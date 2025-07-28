from datetime import timezone, datetime
import json
import os
import random
import uuid
from annotation import api_context_states, utils
import logging
import dateutil
import requests
from annotation.api_context_states import get_dump_jena_request

import re

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

RDF_PREFIXES_DICT = {
"rdfs": "http://www.w3.org/2000/01/rdf-schema#",
"post": "post#",
"annot": "annotation#",
"quest": "question#",
"resp": "response#",
"item": "response_item#",
"human_annot": "human_annotation#",
"human_annot_result": "human_annotation_result#",
}
RDF_PREFIXES = "\n".join([f"PREFIX {k}: <{v}>" for k, v in RDF_PREFIXES_DICT.items()])

QUERY_ENDPOINT = 'query' # name configured at jena-fuseski-folder/run/configuration/some_database.ttl
QUERY_HEADER = {'Content-Type': 'application/sparql-query'}
UPDATE_ENDPOINT = 'update'  # name configured at jena-fuseski-folder/run/configuration/some_database.ttl
UPDATE_HEADER = {'Content-Type': 'application/sparql-update'}

class JenaException(Exception):
    pass

def insert_triples(*triples):
    triples_str = "".join([f' {s} {p} {o} . \n' for  s,p,o in triples])
    command = f"""
    INSERT DATA {{ {triples_str} }}
    """
    command_with_prefixes = f'{RDF_PREFIXES}\n{command}'
    if get_dump_jena_request():
        cache_name = utils.sha256_hash_by_lines(command)
        cache_dir = os.environ["JENA_REQUEST_CACHE"]
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, cache_name), "wt") as dumpfile:
            dumpfile.write(command_with_prefixes)
    res = requests.post(f'{api_context_states.get_rdf_uri()}/{UPDATE_ENDPOINT}', headers=UPDATE_HEADER, data=command_with_prefixes)
    if res.status_code != 204:
        raise JenaException(f'Query: {command_with_prefixes}\n Response: {res}')
    return res.status_code

def get_bindings(command):
    command_with_prefixes = f'{RDF_PREFIXES}\n{command}'
    res = requests.post(f'{api_context_states.get_rdf_uri()}/{QUERY_ENDPOINT}', headers=QUERY_HEADER, data=command_with_prefixes)
    if res.status_code != 200:
        raise JenaException(f'Query: {command_with_prefixes}\n Response: {res}')
    bindings = res.json()["results"]["bindings"]
    return bindings

def batch_retrieve(annot_type, post_ids):
    post_list = " "
    for post_id in post_ids:
        post_list += f"(\"{post_id}\") "
        
    match = re.match(r'^(((.*)_(\d+))_(\d+))$', annot_type)
    
    if match:
        annot_type = match.group(3)
        major = int(match.group(4))
        minor = int(match.group(5))
    else:
        annot_type = annot_type
        major = 1
        minor = 0
    
    
    command = f"""
        SELECT ?p ?text ?time WHERE {{
            ?annot annot:post0 ?post . 
            ?annot annot:timestamp ?time .
            VALUES (?p) {{ {post_list}  }} 
            ?post post:id ?p .
            ?annot annot:quest ?quest .
            ?quest quest:name "{annot_type}" . 
            ?quest quest:major {major} . 
            ?quest quest:minor {minor} . 
            ?annot annot:resp ?resp . 
            ?resp resp:item ?item . 
            ?item item:text ?text
    }}
    """
    
    bindings = get_bindings(command)
        
    return bindings
    
    

##### Human #####


def tag_human_annotation_task(task_id: str, task_name: str):
    insert_triples(
        [f"human_annot:{task_id}", "human_annot:name", utils.sparql_dumps(task_name)],
    )
    
def declare_human_annotation_task(task_id: str, task_name: str, content: str) -> None:
    
    with open("test_write.json", "w") as f:
        f.write(content)
    
    insert_triples(
        [f"human_annot:{task_id}", "human_annot:id", utils.sparql_dumps(task_id)],
        [f"human_annot:{task_id}", "human_annot:content", utils.sparql_dumps(content)],
        [f"human_annot:{task_id}", "human_annot:name", utils.sparql_dumps(task_name)],
        [f"human_annot:{task_id}", "human_annot:declared_at", utils.sparql_dumps(datetime.now(timezone.utc))]
        )

def store_human_annotation_result(task_id: str, annotator: str, result: str) -> None:
    result_id = f"{task_id}_by_{annotator}"
    timestamp = str(datetime.now(timezone.utc))
    submission_id = uuid.uuid4()
    insert_triples(
        [f"human_annot_result:{result_id}", "human_annot_result:submission", f'human_annot_result:{submission_id}'],
        [f"human_annot_result:{result_id}", "human_annot_result:by", utils.sparql_dumps(annotator)],
        [f"human_annot_result:{submission_id}", "human_annot_result:content", utils.sparql_dumps(result)],
        [f"human_annot_result:{submission_id}", "human_annot_result:timestamp", utils.sparql_dumps(timestamp)],
        [f"human_annot:{task_id}", "human_annot:annot", f"human_annot_result:{result_id}"],
        [f"human_annot:{task_id}", "human_annot:last_annotated_at", utils.sparql_dumps(timestamp)]
    )

def get_human_annotation_task(task_name: str | None = None, task_id: str | None = None, annotator: str | None = None, max_count=None, ) -> tuple[str, str] | tuple[None, None]:
    """
    Important! One of task_name or task_id is required. That is, you either tell me the exact task id, or you restrict to some subset of tasks with a name.
    """
    if task_name is None and task_id is None:
        raise ValueError("Either specify task_id or task_name")
    if task_id is None:
        task_uri = f"?task_uri"
    else:
        task_uri = f"human_annot:{task_id}"
    if annotator is not None:
        annotator_filter = f"""
            FILTER NOT EXISTS {{
                {task_uri} human_annot:annot ?result .
            ?result human_annot_result:by {utils.sparql_dumps(annotator)} .
            }}
        """
    else:
        annotator_filter = ""
    if task_name is None:
        task_name_filter = ""
    else:
        task_name_filter = f"{task_uri} human_annot:name {utils.sparql_dumps(task_name)} ."
    cmd =         f"""
        SELECT ?task_id ?content WHERE {{
            {task_uri} human_annot:content ?content .
            {task_uri} human_annot:id ?task_id .
            {task_name_filter}
            {annotator_filter}
            OPTIONAL {{{task_uri} human_annot:annot ?annotation .}}
        }}
        """
    if max_count is not None:
        cmd = cmd + f"""
        GROUP BY ?task_id ?content HAVING (COUNT(distinct ?annotation) < {max_count})
        """
    bindings = get_bindings(
        cmd
    )
    if len(bindings) == 0:
        return None, None
    else:
        binding = random.choice(bindings)
        return binding["task_id"]["value"], binding["content"]["value"]

def get_all_rewritten(major=None, minor=None):
    return get_all_llm_annotation("rewrite", major=major, minor=minor)

def get_all_distill(major=None, minor=None):
    return get_all_static_annotation("distill", major=major, minor=minor)

def get_all_binary(major=None, minor=None):
    return get_all_llm_pair_annotation("binary", major=major, minor=minor)

def get_all_unary(major=None, minor=None):
    return get_all_llm_annotation("unary", major=major, minor=minor)

def get_all_llm_score_relevance(major=None, minor=None):
    return get_all_python_annotation("llm_score_relevance", major=major, minor=minor)

def get_all_llm_score_persuasion(major=None, minor=None):
    return get_all_python_annotation("llm_score_persuasion", major=major, minor=minor)

def get_all_llm_annotation(name, major=None, minor=None):
    bindings = get_bindings(
        f"""SELECT ?id ?text ?time WHERE {{
            ?annot annot:quest ?quest .
            ?annot annot:timestamp ?time .
            ?annot annot:post0 ?post .
            ?post post:id ?id .
            ?quest quest:name "{name}" .
            {("?quest quest:major " + str(major) + " .") if major is not None else ""}
            {("?quest quest:minor " + str(minor) + " .") if minor is not None else ""}
            ?annot annot:resp ?resp .
            ?resp resp:item ?item .
            ?item item:text ?text .
        }}"""
    )
    out = {}
    times = {}
    for binding in bindings:
        id = binding["id"]["value"]
        time = dateutil.parser.parse(binding["time"]["value"])
        text = binding["text"]["value"]
        if id not in times or times[id] < time:
            out[id] = text
            times[id] = time
    return out

def get_all_static_annotation(name, major=None, minor=None):
    bindings = get_bindings(
        f"""SELECT ?id ?text ?time WHERE {{
            ?annot annot:quest ?quest .
            ?annot annot:timestamp ?time .
            ?annot annot:post0 ?post .
            ?post post:id ?id .
            ?quest quest:name "{name}" .
            {("?quest quest:major " + str(major) + " .") if major is not None else ""}
            {("?quest quest:minor " + str(minor) + " .") if minor is not None else ""}
            ?annot annot:resp ?resp .
            ?resp resp:value ?text .
        }}"""
    )
    out = {}
    times = {}
    for binding in bindings:
        id = binding["id"]["value"]
        time = dateutil.parser.parse(binding["time"]["value"])
        text = binding["text"]["value"]
        if id not in times or times[id] < time:
            out[id] = text
            times[id] = time
    return out


def get_all_python_annotation(name, major=None, minor=None):
    bindings = get_bindings(
        f"""SELECT ?id ?text ?time WHERE {{
            ?annot annot:quest ?quest .
            ?annot annot:timestamp ?time .
            ?annot annot:post0 ?post .
            ?post post:id ?id .
            ?quest quest:name "{name}" .
            {("?quest quest:major " + str(major) + " .") if major is not None else ""}
            {("?quest quest:minor " + str(minor) + " .") if minor is not None else ""}
            ?annot annot:resp ?resp .
            ?resp resp:expr ?text .
        }}"""
    )
    out = {}
    times = {}
    for binding in bindings:
        id = binding["id"]["value"]
        time = dateutil.parser.parse(binding["time"]["value"])
        text = eval(binding["text"]["value"])
        if id not in times or times[id] < time:
            out[id] = text
            times[id] = time
    return out

def get_all_llm_pair_annotation(name, major=None, minor=None):
    bindings = get_bindings(
        f"""SELECT ?id0 ?id1 ?text ?time WHERE {{
            ?annot annot:quest ?quest .
            ?annot annot:timestamp ?time .
            ?annot annot:post0 ?post0 .
            ?annot annot:post1 ?post1 .
            ?post0 post:id ?id0 .
            ?post1 post:id ?id1 .
            ?quest quest:name "{name}" .
            {("?quest quest:major " + str(major) + " .") if major is not None else ""}
            {("?quest quest:minor " + str(minor) + " .") if minor is not None else ""}
            ?annot annot:resp ?resp .
            ?resp resp:item ?item .
            ?item item:text ?text .
        }}"""
    )
    out = {}
    times = {}
    for binding in bindings:
        id = (binding["id0"]["value"], binding["id1"]["value"])
        time = dateutil.parser.parse(binding["time"]["value"])
        text = binding["text"]["value"]
        if id not in times or times[id] < time:
            out[id] = text
            times[id] = time
    return out