from __future__ import annotations
from collections import defaultdict
import logging
import os
import re
import threading
from typing import Any

from annotation import utils
from annotation import annotation
from annotation import api_context_states

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def supported_annotations(cmdline_args: dict[str, Any] | None= None ):
    if cmdline_args is None:
        cmdline_args = {}
    supported_annotations = {}
    major_names = set()
    names = set()
    for file in utils.get_all_files(api_context_states.PROMPT_FOLDER[threading.get_native_id()]):
        basename = os.path.basename(file)
        match = re.match(r'^(((.*)_(\d+))_(\d+)).yaml$', basename)
        if match is None:
            logger.warning(f'Ignoring {file} because its filename is not properly formatted as "name_majorver_minorver.yaml"')
            continue
        fullname = match.group(1)
        major_name = match.group(2)
        name = match.group(3)

        major = int(match.group(4))
        minor = int(match.group(5))
        if fullname in supported_annotations:
            raise AssertionError(f"Two copies of {match.group(1)} detected. {file} and {supported_annotations[fullname]['file']}")
        annot = annotation.Annotation(file, name, major, minor, **cmdline_args.get(fullname, {}))

        supported_annotations[match.group(1)] = annot

        latest_name = f"{name}_latest"
        # add as responsible for x.* if has highest minor version
        if major_name not in supported_annotations or supported_annotations[major_name].minor < minor:
            supported_annotations[major_name] = annot # annotation.Annotation(file, name, major, None) # type:ignore
            major_names.add(major_name)
        if name not in supported_annotations or (supported_annotations[name].major, supported_annotations[name].minor) < (major, minor):
            names.add(name)
            supported_annotations[name] = annot #annotation.Annotation(file, name, None, None) # type:ignore
        if (latest_name not in supported_annotations or 
            supported_annotations[latest_name].major < major 
            or  supported_annotations[latest_name].minor < minor):
            supported_annotations[latest_name] = annot
    for major_name in major_names:
        annot_backbone = supported_annotations[major_name]
        supported_annotations[major_name] = annotation.Annotation(annot_backbone.config_path, annot_backbone.name, annot_backbone.major, None, **cmdline_args.get(major_name,  {})) #type:ignore
    for name in names:
        annot_backbone = supported_annotations[name]
        supported_annotations[name] = annotation.Annotation(annot_backbone.config_path, annot_backbone.name, None, None, **cmdline_args.get(name,  {})) #type:ignore
    return supported_annotations


class APIContextManager:

    def __init__(self, cmdline_args=None, prompt_folder=api_context_states.DEFAULT_PROMP_FOLDER, 
                                        mastodon_url=api_context_states.DEFAULT_MASTODON_URL, 
                                        rdf_uri=api_context_states.DEFAULT_RDF_URI,
                                        read_cache=api_context_states.DEFAULT_READ_CACHE,
                                        write_cache=api_context_states.DEFAULT_WRITE_CACHE,
                                        only_cache=api_context_states.DEFAULT_ONLY_CACHE,
                                        dump_jena_request=api_context_states.DEFAULT_DUMP_JENA_REQUEST) -> None:
        self.mastodon_url = mastodon_url
        self.rdf_uri = rdf_uri
        self.prompt_folder = prompt_folder
        self.cmdline_args = cmdline_args if cmdline_args is not None else {}
        self.read_cache = read_cache
        self.write_cache = write_cache
        self.id = threading.get_native_id()
        self.only_cache = only_cache
        self.dump_jena_request = dump_jena_request
        self.result_cache = dict()

    def __enter__(self):
        if threading.get_native_id() != self.id:
            raise ValueError("Should not share SupportedAnnotation context across threads.")
        api_context_states.MASTODON_URL[self.id] = self.mastodon_url
        api_context_states.RDF_URI[self.id] = self.rdf_uri
        api_context_states.PROMPT_FOLDER[self.id] = self.prompt_folder
        api_context_states.READ_CACHE[self.id] = self.read_cache
        api_context_states.WRITE_CACHE[self.id] = self.write_cache
        api_context_states.ONLY_CACHE[self.id] = self.only_cache
        api_context_states.SUPPORTED_ANNOTATIONS[self.id] = supported_annotations(cmdline_args=self.cmdline_args)
        api_context_states.RESULT_CACHE[self.id] = self.result_cache
        api_context_states.DUMP_JENA_REQUEST[self.id] = self.dump_jena_request

    def __exit__(self, exc_type, exc_val, exc_tb):
        if threading.get_native_id() != self.id:
            raise ValueError("Should not share SupportedAnnotation context across threads.")
        del api_context_states.MASTODON_URL[self.id]
        del api_context_states.RDF_URI[self.id]
        del api_context_states.PROMPT_FOLDER[self.id]
        del api_context_states.READ_CACHE[self.id]
        del api_context_states.WRITE_CACHE[self.id]
        del api_context_states.ONLY_CACHE[self.id]
        del api_context_states.SUPPORTED_ANNOTATIONS[self.id]
        del api_context_states.RESULT_CACHE[self.id]
        del api_context_states.DUMP_JENA_REQUEST[self.id]
