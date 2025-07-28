from typing import List, Dict, Any
from annotation import utils
from dotenv import load_dotenv
import os
from openai import OpenAI
import paramiko
import json
import requests
from .llm_response import LLMResponse, LLMOutput, PythonOutput, StaticOutput
from inspect import signature
import logging
from addict import Dict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LLMAnnot:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.allowed_openai_params = set(
            signature(self.client.chat.completions.create).parameters.keys()
        )

        # SSH connection settings for LLAMA
        self.rockfish_host = "login.rockfish.jhu.edu"
        self.rockfish_port = 22
        self.rockfish_username = os.getenv("ROCKFISH_USERNAME")
        self.rockfish_password = os.getenv("ROCKFISH_PASSWORD")
        self.rockfish_endpoint = "http://gpu02:8000/v1/chat/completions"

    def _convert_to_openai_format(self, list_of_dicts):
        messages = []

        for item in list_of_dicts:
            for role, content in item.items():
                if role in ["system", "user", "assistant"]:
                    messages.append({"role": role, "content": content})

        return messages

    def _convert_response(self, responses: List[Any]) -> Dict[int, Dict]:
        result_dict = {}
        for response in responses:
            message = response.message.content
            index = response.index
            logprobs = 0
            logprobs_content = response.logprobs.content
            for logprob in logprobs_content:
                logprobs += logprob.logprob

            result_dict[index] = {"text": message, "logprob": logprobs}
        return result_dict

    def _convert_response_single(self, responses: List[Any]) -> Dict[int, Dict]:
        result_dict = {}
        for i, response in enumerate(responses):
            message = response.token
            logprob = response.logprob

            result_dict[i] = {"text": message, "logprob": logprob}
        return result_dict

    def _convert_type(self, type_name):
        def bool_converter(x):
            if int(x) in [0, 1]:
                return bool(int(x))
            else:
                raise ValueError(x)

        type_mapping = {
            "int": int,
            "str": str,
            "float": float,
            "bool": bool_converter,
            "json": "json",
        }
        return type_mapping.get(type_name, None)

    def _is_valid_json(self, test_string: str) -> bool:
        try:
            json.loads(test_string)
            return True
        except ValueError:
            return False

    def _is_legal_response(
        self, response: str, legal_values: List[Any] | None, response_type
    ) -> bool:
        """
        Check if the response can be converted to the specified type and,
        for non-JSON types, if it is one of the legal values.
        """
        try:
            if response_type != "json":
                response_converted = response_type(response)
                if legal_values is None:
                    return True
                if response_converted in legal_values:
                    return True
            else:
                if self._is_valid_json(response):
                    return True
        except (ValueError, TypeError):
            pass
        return False


    def get_vLLM_response(self, messages, num_answers, **parameter_dict):
        if (
            parameter_dict.get("max_tokens") is None
            or parameter_dict.get("max_tokens") != 1
        ):
            parameter_dict["messages"] = messages
            parameter_dict["logprobs"] = True
            parameter_dict["n"] = num_answers
        elif parameter_dict.get("max_tokens") == 1:
            parameter_dict["messages"] = messages
            parameter_dict["logprobs"] = True
            parameter_dict["top_logprobs"] = num_answers

        payload_json = json.dumps(parameter_dict, ensure_ascii=False)

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh_client.connect(
                hostname=self.rockfish_host,
                port=self.rockfish_port,
                username=self.rockfish_username,
                password=self.rockfish_password,
                timeout=600,
            )
            print("SSH connection established.")

            payload_json_escaped = payload_json.replace("'", "'\\''")
            command = f'curl -X POST {self.rockfish_endpoint} -H "Content-Type: application/json" -d \'{payload_json_escaped}\''
            stdin, stdout, stderr = ssh_client.exec_command(command)
            response = stdout.read().decode("utf-8")
            return Dict(json.loads(response))

        except paramiko.AuthenticationException:
            print("Authentication failed. Please check your username and password.")
        except paramiko.SSHException as e:
            print("Unable to establish SSH connection:", str(e))
        finally:
            ssh_client.close()

    def get_top_n_responses(
        self,
        prompt: List[Dict],
        legal_answer_type,
        num_answers: int = 1,
        legal_answers: List[Any] = None,
        method="openai",
        **parameter_dict,
    ):
        """
        Get the top-n responses from the OpenAI API, filtering out any response that cannot be converted to the specified type or is not within legal values.
        paremeter_dict must be available OpenAI API parameters.
        """
        messages = self._convert_to_openai_format(prompt)
        if method in {"openai", "vLLM"}:
            if (
                parameter_dict.get("max_tokens") is None
                or parameter_dict.get("max_tokens") != 1
            ):
                if method == "openai":
                    top_choices = self.client.chat.completions.create(
                        messages=messages,
                        n=num_answers,
                        logprobs=True,
                        **parameter_dict,
                    ).choices
                elif method == "vLLM":
                    top_choices = self.get_vLLM_response(
                        messages, num_answers, **parameter_dict
                    ).choices
                result_dict = self._convert_response(top_choices)
            elif parameter_dict.get("max_tokens") == 1:
                if method == "openai":
                    top_choices = (
                        self.client.chat.completions.create(
                            messages=messages,
                            logprobs=True,
                            top_logprobs=num_answers,
                            **parameter_dict,
                        )
                        .choices[0]
                        .logprobs.content[0]
                        .top_logprobs
                    )
                elif method == "vLLM":
                    top_choices = (
                        self.get_vLLM_response(messages, num_answers, **parameter_dict)
                        .choices[0]
                        .logprobs.content[0]
                        .top_logprobs
                    )
                result_dict = self._convert_response_single(top_choices)
        elif method == "human":
            utils.pretty_print_human(messages)
            annotation = input("Enter your annotation result: ")
            result_dict = {0: {"text": annotation, "logprob": "dummy"}}
        else:
            raise NotImplementedError(f"{method} not implemented")

        legal_answer_type_orig = legal_answer_type
        legal_answer_type = self._convert_type(legal_answer_type)

        output = []
        for index, result in result_dict.items():
            if (
                self._is_legal_response(
                    result["text"], legal_answers, legal_answer_type
                )
                and legal_answer_type != "json"
            ):
                output.append(
                    LLMResponse(
                        annotation=legal_answer_type(result["text"]),
                        rank=index,
                        logprobs=result["logprob"],
                        text=result["text"],
                    )
                )
            elif (
                self._is_legal_response(
                    result["text"], legal_answers, legal_answer_type
                )
                and legal_answer_type == "json"
            ):
                output.append(
                    LLMResponse(
                        annotation=json.loads(result["text"]),
                        rank=index,
                        logprobs=result["logprob"],
                        text=result["text"],
                    )
                )

        if output != []:
            output = sorted(output, key=lambda x: x.rank)
            from_LLM = LLMOutput(responses=output, additional_info=parameter_dict)
            from_LLM.update_additional_info(
                {"method": method, 'legal_answer_type': legal_answer_type_orig}
            )
            return from_LLM
        else:
            raise ValueError(f"No legal annotations are output! {result_dict}")

    def get_responses(self, method, **kwargs):
        if method in {"openai", "vLLM", "human"}:
            prompt = kwargs.pop("prompt")
            legal_answer_type = kwargs.pop("legal_answer_type")
            num_answers = kwargs.pop("num_answers", 1)
            legal_answers = kwargs.pop("legal_answers", None)
            if method == "openai":
                parameter_dict = {}
                for k, v in kwargs.items():
                    if k not in self.allowed_openai_params:
                        logger.warning(f"{k} not used in openai create api, ignoring")
                        continue
                    parameter_dict[k] = v
            else:
                parameter_dict = kwargs

            return self.get_top_n_responses(
                prompt=prompt,
                legal_answer_type=legal_answer_type,
                num_answers=num_answers,
                legal_answers=legal_answers,
                method=method,
                **parameter_dict,
            )
        elif method == "static":
            return StaticOutput(kwargs["value"])
        elif method == "python":
            return PythonOutput(kwargs["expr"])


if __name__ == "__main__":
    # Test final output codes
    annot = LLMAnnot()

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "You will be given one social media post. You should decide how funny or humorous this post is. Your answer should be a number from 0 to 11 inclusively. 0 indicates not funny at all and 11 indicates very funny. Answer with a single number, do not give reasoning or explain it.\nFirst post: '''So Colin kaepernick just signed a shoe deal with Nike. I didn\\u2019t know you needed shoes to kneel... Bah dum tish'''\nAnswer:\n",
        },
    ]
    test = annot.get_vLLM_response(
        messages,
        1,
        **{"model": "meta-llama/Meta-Llama-3-8B-Instruct", "temperature": 0.5},
    )
    print("Test:", test)