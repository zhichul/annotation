import re
from typing import List, Dict, Any
import math
import uuid
import addict
from annotation import utils, cache
import json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class OutdatedCacheImplementationException(Exception):
    pass

class LLMResponse:
    def __init__(self, annotation: Any, rank: int, logprobs: float, text: str):
        self.annotation = annotation
        self.rank = rank
        self.logprobs = logprobs
        self.text = text

    def __repr__(self):
        return (
            f"LLMResponse(annotation={self.annotation!r}, rank={self.rank!r}, logprobs={self.logprobs!r}, "
            f"text={self.text!r})"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annotation": self.annotation,
            "rank": self.rank,
            "logprobs": self.logprobs,
            "text": self.text,
        }

    @property
    def probability(self) -> float:
        return math.exp(self.logprobs)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMResponse":
        return cls(
            annotation=data["annotation"],
            rank=data["rank"],
            logprobs=data["logprobs"],
            text=data["text"],
        )


class LLMOutput:
    def __init__(
        self,
        responses: List[LLMResponse] | None = None,
        additional_info: Dict[str, Any] | None = None,
    ):
        self.responses = responses if responses is not None else []
        self.additional_info = additional_info if additional_info is not None else {}

    def __repr__(self):
        return f"LLMOutput(responses={self.responses!r}, additional_info={self.additional_info!r})"

    def __str__(self) -> str:
        return str(self.responses[0].annotation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "responses": [response.to_dict() for response in self.responses],
            "additional_info": self.additional_info,
        }

    def get_response(self, index: int) -> LLMResponse:
        return self.responses[index]

    def get_additional_info(self, key: str) -> Any:
        return self.additional_info.get(key, None)

    def update_additional_info(self, info: Dict[str, Any]):
        if not isinstance(info, dict):
            raise TypeError("The input must be a dictionary")
        self.additional_info.update(info)

    @property
    def distribution(self) -> Dict[Any, float]:
        assert (
            self.additional_info.get("max_tokens") == 1
        ), "The distribution is only available for max_tokens=1"
        distributions = {}
        total_prob = sum(response.probability for response in self.responses)
        for response in self.responses:
            prob = response.probability
            distributions[response.annotation] = prob / total_prob
        return distributions

    @property
    def mean(self) -> float:
        for response in self.responses:
            if not isinstance(response.annotation, (int, float)):
                raise ValueError("The mean is only available for numerical annotations")
        return sum(response.annotation for response in self.responses) / len(
            self.responses
        )

    def cache_response(self) -> str:
        lists_of_annotations = []
        id = uuid.uuid4()
        for k, v in self.additional_info.items():
            single_list = [f"resp:{id}", f"resp:{k}",  utils.sparql_dumps(v)]
            lists_of_annotations.append(single_list)
        for response in self.responses:
            item_id = uuid.uuid4()
            single_list = [
                f"resp:{id}",
                "resp:item",
                f"item:{item_id}",
            ]
            lists_of_annotations.append(single_list)
            for k, v in response.to_dict().items():
                if isinstance(v, dict) or isinstance(v, list):
                    single_list = [f"item:{item_id}", f"item:{k}", utils.sparql_dumps(json.dumps(v))]
                else:
                    single_list = [f"item:{item_id}", f"item:{k}", utils.sparql_dumps(v)]

                lists_of_annotations.append(single_list)
        cache.insert_triples(*lists_of_annotations)
        uri = f"resp:{id}"
        return uri

    @property
    def value(self):
        return self.responses[0].annotation

    def __getattr__(self, name):
        return getattr(self.responses[0].annotation, name)

class StaticOutput:
    def __init__(self, value):
        self.value = value

    def __repr__(self) -> str:
        return f"StaticOutput(value={self.value!r})"

    def __str__(self) -> str:
        return str(self.value)

    def cache_response(self) -> str:
        lists_of_annotations = []
        id = uuid.uuid4()
        method_list = [f"resp:{id}", "resp:method", '"static"']
        value_list = [f"resp:{id}", "resp:value", utils.sparql_dumps(json.dumps(self.value))]
        lists_of_annotations.append(method_list)
        lists_of_annotations.append(value_list)
        cache.insert_triples(*lists_of_annotations)
        return f"resp:{id}"

class PythonOutput:
    def __init__(self, expr):
        self.expr = expr
    
    @property
    def value(self):
        return eval(self.expr)

    def __repr__(self) -> str:
        return f"PythonOutput(expr={self.expr!r})"

    def __str__(self) -> str:
        return str(self.expr)

    def cache_response(self) -> str:
        lists_of_annotations = []
        id = uuid.uuid4()
        method_list = [f"resp:{id}", "resp:method", '"python"']
        expr_list = [f"resp:{id}", "resp:expr", utils.sparql_dumps(self.expr)]
        lists_of_annotations.append(method_list)
        lists_of_annotations.append(expr_list)
        cache.insert_triples(*lists_of_annotations)
        return f"resp:{id}"


def extract_after_base_url(base_url, target_string):
    regex_pattern = rf"^{base_url}(.*?)$"
    match = re.match(regex_pattern, target_string)
    if match:
        return match.group(1)
    return None


def convert_type(type_name):
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


def get_cached_response(uri: str) -> LLMOutput:
    command = f"""
    SELECT ?k ?v WHERE {{
        {uri} ?k ?v
    }}
    """
    bindings = cache.get_bindings(command)
    """bindings example
    [
        {"k": {"type": some_type, "value": some_value}, 
         "v": {"type": some_type, "value": some_value}},
         ...
    ]
    """
    items = []
    additional_info = {}
    for binding in bindings:
        k_full = binding["k"]["value"]
        v_full = binding["v"]["value"]
        k_match = extract_after_base_url(cache.RDF_PREFIXES_DICT["resp"], k_full)
        if k_match is None:
            raise ValueError("We could not find corresponding key in the cache.")
        if k_match == "item":
            if binding["v"]["type"] != "uri":
                raise ValueError("There must be a valid uri!")
            item_command = f"""
            SELECT ?k ?v WHERE {{
                <{v_full}> ?k ?v
            }}
            """
            item_bindings = cache.get_bindings(item_command)
            item_dict = {}
            for item_binding in item_bindings:
                item_k = item_binding["k"]["value"]
                item_v = item_binding["v"]["value"]
                item_k_name = extract_after_base_url(
                    cache.RDF_PREFIXES_DICT["item"], item_k
                )
                if item_k_name == "logprobs":
                    item_v = float(item_v)
                item_dict[item_k_name] = item_v
            items.append(item_dict)
        elif k_match == "max_tokens" or k_match == "rank":
            additional_info[k_match] = int(v_full)
        elif k_match == "temperature":
            additional_info[k_match] = float(v_full)
        else:
            additional_info[k_match] = v_full

    if additional_info.get("method") == "static":
        try:
            return StaticOutput(json.loads(additional_info["value"])) # type:ignore
        except:
            raise OutdatedCacheImplementationException("StaticOutput needs to be jsondumped in new version. Backwards compatibility is not implemented. Invalidating cache.")
    if additional_info.get("method") == "python":
        return PythonOutput(additional_info["expr"]) # type:ignore
    else:
        responses = []
        for item in items:
            valid_type = additional_info.get("legal_answer_type", None)
            if valid_type is None:
                raise OutdatedCacheImplementationException("The legal_answer_type is not properly cached.")
            valid_type = convert_type(valid_type)
            if valid_type is not None and valid_type != "json":
                item["annotation"] = valid_type(item["annotation"])
            elif valid_type == "json":
                try:
                    item["annotation"] = addict.Dict(json.loads(item["annotation"]))
                except:
                    item["annotation"] = addict.Dict(json.loads(item["annotation"][1:-1]))
            responses.append(LLMResponse.from_dict(item))
        return LLMOutput(responses=responses, additional_info=additional_info)


def coerce(llm_output: LLMOutput):
    return llm_output.responses[0].annotation


utils.overload_ops(LLMOutput, coersion=coerce)
