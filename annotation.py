from datetime import datetime, timezone
import functools
import json
import os
import re
from typing import Iterable
import uuid
from annotation import llm_response 
import dateutil
import requests
import yaml
from jinja2 import Environment, StrictUndefined
from annotation import llm_wrapper, utils, api_context_states, cache, post
import logging
import builtins

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

llm_annot = llm_wrapper.LLMAnnot()

@functools.cache
def indent_template(template):
    doc = []
    for line in template.splitlines():
        ws = len(line) - len(line.lstrip())
        doc.append(re.sub("{{([^{}]*)}}", lambda s: f"{{{{ str({s.group(1)}) | indent({ws})}}}}", line))
    return "\n".join(doc)

class Annotation:

    def __init__(self, config_path: str, name: str, major: int, minor: int, **cmdline_override_args):
        self.config_path = config_path
        self.name = name
        self.major = major
        self.minor = minor
        basename = os.path.basename(config_path)
        match = re.match(r'^(((.*)_(\d+))_(\d+)).yaml$', basename)
        self.parsed_major = int(match.group(4)) # type:ignore
        self.parsed_minor = int(match.group(5)) # type:ignore
        with open(config_path, "rt") as f:
            self.documents = utils.split_yaml_docs(f.read())
        if not len(self.documents) == 2:
            raise ValueError(f"{config_path} does not contain exactly two yaml docs.")
        
        self.spec = yaml.safe_load(self.documents[0])
        if self.spec is None:
            self.spec = dict()
        self.default_args = self.spec.get("args", dict())
        self.alias = self.spec.get("alias", dict())
        self.cmdline_override_args = cmdline_override_args
        self._env = Environment(undefined=StrictUndefined)
        self.rendered_last_doc = indent_template(self.documents[-1])
        
    def _get_overidden_args(self, **caller_override_args):
        args = utils.nested_copy_dict(self.default_args) # default is lowest priority
        try:
            utils.nested_update_dict(args, caller_override_args, strict=True) # yaml is second highest priority
            utils.nested_update_dict(args, self.cmdline_override_args, strict=True) # command line is highest priority
        except ValueError as e:
            logging.error("You tried to override an argument that was not declared in `args` of the yaml file. Did you maybe make a typo? In the following error message old refers to declared variables, and new refers to overriding values.")
            raise e
        return args

    def _augment_args_for_interpolation(self, *posts, **args):
        interpolation_args = utils.nested_copy_dict(args)
        for i, post in enumerate(posts):
            interpolation_args[f"post{i}"] = post
        return interpolation_args

    def _render_jinja2(self, *posts, **interpolation_args):
        interpolation_args_aliased = utils.nested_copy_dict(interpolation_args)
        interpolation_args_aliased["post"] = posts[0]
        interpolation_args_aliased[f"posts"] = posts
        for name in dir(builtins):
            interpolation_args_aliased[name] = getattr(builtins, name)
        s = utils.render_with_alias(self._env, self.rendered_last_doc, self.alias, **interpolation_args_aliased)
        return s

    def _execute_prompt(self, annotation_args, override_args):
        default_method = annotation_args.get("method", "openai")
        if default_method == "static" and "method" in override_args:
            # static methods cannot be overriden
            del override_args["method"]
        annotation_args.update(override_args) # override with args, which has precedence order file -> caller -> cmdline
        logger.info(f"Annot args: {json.dumps(annotation_args, indent=2, sort_keys=True)}")
        if default_method == "openai":
            logger.debug(f"Pretty dialogue:\n")
            for msg in annotation_args["prompt"]:
                for role, msg_content in msg.items():
                    msg_content = "\n\t> " + msg_content.replace('\n', '\n\t > ')
                    logger.debug(f"{role}: {msg_content}")
        method = annotation_args.pop("method", "openai")
        response = llm_annot.get_responses(method, **annotation_args) 
        response.timestamp = str(datetime.now(timezone.utc)) # type:ignore
        return response

    def __call__(self, *posts: post.Edit, **caller_override_args):
        # bookkeeping for logging recursive dependencies
        call_stack = api_context_states.get_call_stack()
        call_stack.enter(name=self.name, major=self.major, minor=self.minor, sha256=self.sha256_quest)

        # logging info
        post_str = '\n> '.join([repr(post) for post in posts])
        logger.info(f"\n\n> {self.name}_{self.major}{f'({self.parsed_major})' if self.major is None else ''}_{self.minor}{f'({self.parsed_minor})' if self.major is None else ''}  called on \n> {post_str}\n")

        ##### Step 0: assemble arguments and see if cache hit #####
        args = self._get_overidden_args(**caller_override_args)
        interpolation_args = self._augment_args_for_interpolation(*posts, **args)

        # we hash here
        ##### lookup from cache ####
        thread_cache = api_context_states.get_result_cache()
        if (self.sha256_quest, *tuple(posts), *sorted(caller_override_args.items())) in thread_cache:
            cached_response = thread_cache[(self.sha256_quest, *tuple(posts), *sorted(caller_override_args.items()))]
            logger.info(f"returning memory cached response from {cached_response.timestamp}") # type:ignore
            return cached_response
        if api_context_states.get_read_cache():
            cached_response, dependencies, quest = self.get_cached_annotation(interpolation_args)
            
            if cached_response is not None:
                logger.info(f"returning jena cached response from {cached_response.timestamp}") # type:ignore
                call_stack.current.dependencies = dependencies
                call_stack.current.major = quest.major # type:ignore
                call_stack.current.minor = quest.minor # type:ignore
                call_stack.current.sha256 = quest.sha256 # type:ignore
                call_stack.exit()
                thread_cache[(self.sha256_quest, *tuple(posts), *sorted(caller_override_args.items()))] = cached_response
                return cached_response
            elif api_context_states.get_only_cache():
                # if only cache mode and result not in cache, return None
                thread_cache[(self.sha256_quest, *tuple(posts), *sorted(caller_override_args.items()))] = None
                call_stack.exit()
                return None

 
        ##### Step 1: call JINJA2 to fill in templated called to LLM  #####
        yaml_s = self._render_jinja2(*posts, **interpolation_args)
        annotation_args = yaml.safe_load(yaml_s) # lowest priority parameters (even compared to the args listed at the top)

        ##### Step 2: call the LLM using arguments defined in the yaml file #####
        response = self._execute_prompt(annotation_args, args)
        if api_context_states.get_write_cache():
            self.cache_annotation(posts, interpolation_args, response, call_stack.current.dependencies) # type: ignore
        thread_cache[(self.sha256_quest, *tuple(posts), *sorted(caller_override_args.items()))] = response
        call_stack.exit()
        return response

    def render_parse(self, *posts, **caller_override_args):
        post_str = '\n> '.join([repr(post) for post in posts])
        logger.info(f"\n\n> {self.name}_{self.major}_{self.minor} called on \n> {post_str}\n")
        args = self._get_overidden_args(**caller_override_args)
        interpolation_args = self._augment_args_for_interpolation(*posts, **args)
        s = self._render_jinja2(*posts, **interpolation_args)
        annotation_args = yaml.safe_load(s) # lowest priority parameters (even compared to the args listed at the top)
        return annotation_args

    def __repr__(self):
        return f"Annotation({self.name}, {self.major}, {self.minor}, **{str(self.cmdline_override_args)})"

    def sha256_call(self, args):
        return utils.sha256_hash_by_lines(json.dumps(args, sort_keys=True, default = lambda x: str(x)))

    @property
    def sha256_quest(self):
        return utils.sha256_hash_by_lines(*[self.name, 
                                            str(self.parsed_major if not self.major else self.major), 
                                            str(self.parsed_minor if not self.minor else self.minor), 
                                            *self.documents])

    def cache_annotation(self, edits: Iterable[post.Edit], hash_args: dict, response: llm_response.LLMOutput, dependencies: list[utils.Quest]):
        """
        hash_args is the args that define the hash
        annotation_args is the args that was sent to the LLM call

        We cache by hash_args, even though multiple hash_args may result in the same annotation_args, because we want to be able to
        hit cache without assembing the LLM call, since it's expensive (has to call Jena recursively).
        """
        quest_uri = cache_question(self)
        edit_uris = [cache_edit(edit) for edit in edits]
        response_uri = response.cache_response()

        id = uuid.uuid4()
        sha256 = self.sha256_call(hash_args)
        post_connections = [[f"annot:{id}", f"annot:post{i}", edit_uri] for i, edit_uri in enumerate(edit_uris)]
        quest_connections = [[f"annot:{id}", f"annot:quest", quest_uri]]
        timestamp_connections = [[f"annot:{id}", "annot:timestamp", utils.sparql_dumps(response.timestamp)]] # type:ignore
        response_connections = [[f"annot:{id}", "annot:resp", response_uri]]
        hash_connections = [[f"annot:{id}", "annot:call_hash",  utils.sparql_dumps(sha256)]]
        user_connections = [[f"annot:{id}", "annot:run_by",  utils.sparql_dumps(os.environ.get('USER', os.environ.get('USERNAME')))]]
        commit_connections = [[f"annot:{id}", "annot:git_commit",  utils.sparql_dumps(utils.get_git_revision_hash())],
                            [f"annot:{id}", "annot:git_branch",  utils.sparql_dumps(utils.get_git_branch())]]
        dependency_connections = [[f"annot:{id}", "annot:dep", f"quest:{dep.sha256}"] for dep in dependencies]
        cache.insert_triples(
            *(post_connections 
            + quest_connections 
            + timestamp_connections 
            + response_connections 
            + hash_connections 
            + user_connections
            + commit_connections
            + dependency_connections)
        )
        return f"annot:{id}"

        
    def get_cached_annotation(self, hash_args: dict):
        resp_uri, timestamp, dependencies, quest = self.get_response_uri_and_timestamp_by_annotation_hash(hash_args) # type:ignore
        
        if resp_uri is not None:
            try:
                result = llm_response.get_cached_response(f"<{resp_uri}>")
                result.timestamp = timestamp # type:ignore
                return result, dependencies, quest
            except llm_response.OutdatedCacheImplementationException as e:
                logger.warning("Caching code updated significantly so that cache is no longer compatible with new version, invalidating cache.")
                return None, None, None
        return None, None, None

    def get_response_uri_and_timestamp_by_annotation_hash(self, hash_args:dict, method="latest") -> tuple[str, str, list[utils.Quest], utils.Quest] | tuple[None, None, None, None]:
        sha256 = self.sha256_call(hash_args)
        command = f"""
        SELECT ?annot ?major ?minor ?resp ?time ?qhash WHERE {{ 
            ?annot annot:resp ?resp .
            ?annot annot:call_hash "{sha256}" .
            ?annot annot:timestamp ?time .
            ?annot annot:quest ?quest .
            ?quest quest:name "{self.name}" .
            ?quest quest:major ?major .
            {("?quest quest:major " + str(self.major) + " .") if self.major is not None else ""}
            ?quest quest:minor ?minor .
            {("?quest quest:minor " + str(self.minor) + " .") if self.minor is not None else ""}
            ?quest quest:hash ?qhash .
            VALUES ?qhash {{ {api_context_states.question_hashes_sparql(" ")} }}
            FILTER NOT EXISTS {{
                ?annot annot:dep ?quest_dep .
                ?quest_dep quest:hash ?qdep_hash .
                FILTER (?qdep_hash NOT IN ({api_context_states.question_hashes_sparql(", ")}))
            }}
        }}
        """
        bindings = cache.get_bindings(command)
        
        if len(bindings) == 0:
            return None, None, None, None
        if len(bindings) == 1:
            binding = bindings[0]
        if len(bindings) > 1:
            if method == "latest":
                logger.warning("Multiple cached entries, using latest matching version (and latest time) by default.")
                binding = max(bindings, key=lambda binding: 
                               (int(binding["major"]["value"]), 
                                int(binding["minor"]["value"]), 
                                dateutil.parser.parse(binding["time"]["value"]))) # type:ignore
            else:
                raise NotImplementedError(f"list resolution method not implemented: {method}")
        dependencies_command = f"""
        SELECT * WHERE {{
            <{binding["annot"]["value"]}> annot:dep ?quest_dep .
            ?quest_dep quest:name ?name .
            ?quest_dep quest:major ?major .
            ?quest_dep quest:minor ?minor .
            ?quest_dep quest:hash ?hash .
        }}
        """
        dependencies_bindings = cache.get_bindings(dependencies_command)
        return (binding["resp"]["value"], 
                binding["time"]["value"], 
                [utils.Quest(name=b["name"]["value"],
                    major=int(b["major"]["value"]), 
                    minor=int(b["minor"]["value"]),
                    sha256=b["hash"]["value"]) for b in dependencies_bindings],
                utils.Quest(name=self.name, major=int(binding["major"]["value"]), minor=int(binding["minor"]["value"]), sha256=binding["qhash"]["value"]))

class BoundAnnotation:

    def __init__(self, f: Annotation, *args, **kwargs) -> None:
        self.f = f
        self.args = args
        self.kwargs = kwargs
    
    def __call__(self, *args, **kwargs):
        for key in kwargs:
            if key in self.kwargs:
                raise ValueError(f"{key} already bound to {self.kwargs[key]}")
        self.kwargs.update(kwargs)
        return self.f(*(self.args + args), **self.kwargs)

    @utils.escape_double_quotes_decorator
    def __str__(self) -> str:
        res = self.f(*self.args, **self.kwargs)
        return str(res)

    def __getattr__(self, name):
        if name == "jinja_pass_arg":
            raise AttributeError()
        return getattr(self(), name)

    def render_parse(self, *args, **kwargs):
        for key in kwargs:
            if key in self.kwargs:
                raise ValueError(f"{key} already bound to {self.kwargs[key]}")
        self.kwargs.update(kwargs)
        return self.f.render_parse(*(self.args + args), **self.kwargs)



def coerce(bound_annotation: BoundAnnotation):
    return bound_annotation()

utils.overload_ops(BoundAnnotation, coersion=coerce)

def cache_edit(edit: post.Edit):
    # type:ignore
    sha256 = edit.sha256
    cache.insert_triples(
        [f"post:{sha256}", "post:id",  utils.sparql_dumps(edit.mastodon_id)],
        [f"post:{sha256}", "post:timestamp",  utils.sparql_dumps(edit.timestamp)],
        [f"post:{sha256}", "post:content",  utils.sparql_dumps(edit.content)],
    )
    return f"post:{sha256}"

def cache_question(annot: Annotation):
    sha256 = annot.sha256_quest
    cache.insert_triples(
        [f"quest:{sha256}", "quest:name",  utils.sparql_dumps(annot.name)],
        [f"quest:{sha256}", "quest:major", annot.major if annot.major is not None else annot.parsed_major],
        [f"quest:{sha256}", "quest:minor", annot.minor if annot.minor is not None else annot.parsed_minor],
        [f"quest:{sha256}", "quest:hash",  utils.sparql_dumps(sha256)],
    )
    return f"quest:{sha256}"




    