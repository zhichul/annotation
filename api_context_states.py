# states per thread, integer is the thread native_id
# use defaultdicts to support when calling without a context manager
from collections import defaultdict
import functools
import os
import threading
from typing import Any

from annotation import utils
import dotenv
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()
DEFAULT_MASTODON_URL = os.environ["MASTODON_API_URL"]
DEFAULT_RDF_URI = os.environ["RDF_URI"]
DEFAULT_PROMP_FOLDER = os.getenv("PROMPT_FOLDER_OVERRIDE", os.environ["PROMPT_FOLDER"])
DEFAULT_READ_CACHE = True
DEFAULT_WRITE_CACHE = True
DEFAULT_ONLY_CACHE = False
DEFAULT_DUMP_JENA_REQUEST = False

MASTODON_URL: dict[int, str] = defaultdict(lambda: DEFAULT_MASTODON_URL)
RDF_URI: dict[int, str] = defaultdict(lambda: DEFAULT_RDF_URI)
PROMPT_FOLDER: dict[int, str] = defaultdict(lambda: DEFAULT_PROMP_FOLDER)
READ_CACHE: dict[int, bool] = defaultdict(lambda: DEFAULT_READ_CACHE)
WRITE_CACHE: dict[int, bool] = defaultdict(lambda: DEFAULT_WRITE_CACHE)
ONLY_CACHE: dict[int, bool] = defaultdict(lambda: DEFAULT_ONLY_CACHE)
CALL_STACK: dict[int, Any] = defaultdict(utils.CallStack)
RESULT_CACHE: dict[int, dict] = defaultdict(lambda: dict())
DUMP_JENA_REQUEST: dict[int, bool] = defaultdict(lambda: DEFAULT_DUMP_JENA_REQUEST)

def get_mastodon_url(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return MASTODON_URL[thread_id]

def get_prompt_folder(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return PROMPT_FOLDER[thread_id]

def get_rdf_uri(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return RDF_URI[thread_id]

def get_read_cache(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return READ_CACHE[thread_id]

def get_write_cache(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return WRITE_CACHE[thread_id]

def get_only_cache(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return ONLY_CACHE[thread_id]

def get_result_cache(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return RESULT_CACHE[thread_id]

def get_dump_jena_request(thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return DUMP_JENA_REQUEST[thread_id]

def default_supported_annotations():
    from annotation.api_context_manager import supported_annotations
    return supported_annotations()

SUPPORTED_ANNOTATIONS: dict[int, dict[str, Any]] = defaultdict(default_supported_annotations)  # not declare type because circula dependency on annotation

def get_supported_annotation(name, thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return SUPPORTED_ANNOTATIONS[thread_id][name]

def is_supported_annotation(name, thread_id=None):
    if thread_id is None:
        thread_id = threading.get_native_id()
    return name in SUPPORTED_ANNOTATIONS[thread_id]

def get_call_stack(thread_id=None) -> utils.CallStack:
    if thread_id is None:
        thread_id = threading.get_native_id()
    return CALL_STACK[thread_id]

@functools.cache
def question_hashes():
    hashes = []
    for k, v in default_supported_annotations().items():
        if v.major is not None and v.minor is not None:
            hashes.append(v.sha256_quest)
    return hashes

@functools.cache
def question_hashes_sparql(join=", "):
    return join.join([f'"{h}"' for h in question_hashes()])