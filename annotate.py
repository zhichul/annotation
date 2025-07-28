#!/usr/bin/env python3
from argparse import ArgumentParser, Action
import copy
from datetime import datetime
from dateutil import tz
import dateutil
from annotation import main, post
import logging
from annotation import api_context_manager, api_context_states

import dateutil.parser
LOCAL_TIMEZONE_NAME = 'US/Eastern'
LOCAL_TIMEZONE = tz.gettz(LOCAL_TIMEZONE_NAME)


class ParseKwargs(Action):
    """
    https://sumit-ghosh.com/posts/parsing-dictionary-key-value-pairs-kwargs-argparse-python/
    """
    def __call__(self, parser, namespace, values, option_string=None): # type:ignore
        setattr(namespace, self.dest, dict())
        for value in values: # type:ignore
            key, value = value.split('=')
            # try to convert to int and float
            try:
                value = int(value)
            except:
                try:
                    value = float(value)
                except:
                    value = value
            getattr(namespace, self.dest)[key] = value

def run_single(args):
    if args.post_time is None:
        if args.post_id is None:
            edit = post.EditFromFile(args.post_file)
        else:
            edit = post.Post(args.post_id).latest()
    else:
        edit = post.Edit.new(args.post_id,  dateutil.parser.parse(args.post_time)) # type:ignore
    overrides = {k: copy.copy(args.args_global) for k in api_context_states.default_supported_annotations()}
    overrides[args.annotation].update(args.args)
    result = main.annotate(args.annotation, [edit], no_read=args.no_read_from_cache or args.no_cache, no_write=args.no_write_to_cache or args.no_cache, only_cache=args.only_cache, cmdline_args=overrides)
    print("---")
    print("Question:      ", args.annotation)
    print("Post ID:       ", args.post_id)
    print("Post Timestamp:", edit.timestamp)
    print("---")
    if result is not None:
        print(f"Annotation Timestamp ({LOCAL_TIMEZONE_NAME}):", datetime.astimezone(dateutil.parser.parse(result.timestamp), LOCAL_TIMEZONE))
        print("Annotation Response:", result)
    else:
        print(f"Annotation Timestamp ({LOCAL_TIMEZONE_NAME}):", "null")
        print("Annotation Response:", "null")

def run_pair(args):
    if args.post0_time is None:
        if args.post0_id is None:
            edit0 = post.EditFromFile(args.post0_file)
        else:
            edit0 = post.Post(args.post0_id).latest()
    else:
        edit0 = post.Edit.new(args.post0_id,  dateutil.parser.parse(args.post0_time)) # type:ignore
    if args.post1_time is None:
        if args.post1_id is None:
            edit1 = post.EditFromFile(args.post1_file)
        else:
            edit1 = post.Post(args.post1_id).latest()
    else:
        edit1 = post.Edit.new(args.post1_id,  dateutil.parser.parse(args.post1_time)) # type:ignore
    overrides = {k: copy.copy(args.args_global) for k in api_context_states.default_supported_annotations()}
    overrides[args.annotation].update(args.args)
    result = main.annotate(args.annotation, [edit0, edit1], no_read=args.no_read_from_cache or args.no_cache, no_write=args.no_write_to_cache or args.no_cache, only_cache=args.only_cache, cmdline_args=overrides)
    print("---")
    print("Question:       ", args.annotation)
    print("Post0 ID:       ", args.post0_id)
    print("Post0 Timestamp:", edit0.timestamp)
    print("Post1 ID:       ", args.post1_id)
    print("Post1 Timestamp:", edit1.timestamp)
    print("---")
    if result is not None:
        print(f"Annotation Timestamp ({LOCAL_TIMEZONE_NAME}):", datetime.astimezone(dateutil.parser.parse(result.timestamp), LOCAL_TIMEZONE))
        print("Annotation Response:", result)
    else:
        print(f"Annotation Timestamp ({LOCAL_TIMEZONE_NAME}):", "null")
        print("Annotation Response:", "null")

def run_triple(args):
    if args.post0_time is None:
        if args.post0_id is None:
            edit0 = post.EditFromFile(args.post0_file)
        else:
            edit0 = post.Post(args.post0_id).latest()
    else:
        edit0 = post.Edit.new(args.post0_id,  dateutil.parser.parse(args.post0_time)) # type:ignore
    if args.post1_time is None:
        if args.post1_id is None:
            edit1 = post.EditFromFile(args.post1_file)
        else:
            edit1 = post.Post(args.post1_id).latest()
    else:
        edit1 = post.Edit.new(args.post1_id,  dateutil.parser.parse(args.post1_time)) # type:ignore
    if args.post2_time is None:
        if args.post2_id is None:
            edit2 = post.EditFromFile(args.post2_file)
        else:
            edit2 = post.Post(args.post2_id).latest()
    else:
        edit2 = post.Edit.new(args.post2_id,  dateutil.parser.parse(args.post2_time)) # type:ignore
    overrides = {k: copy.copy(args.args_global) for k in api_context_states.default_supported_annotations()}
    overrides[args.annotation].update(args.args)
    result = main.annotate(args.annotation, [edit0, edit1, edit2], no_read=args.no_read_from_cache or args.no_cache, no_write=args.no_write_to_cache or args.no_cache, only_cache=args.only_cache, cmdline_args=overrides)
    print("---")
    print("Question:       ", args.annotation)
    print("Post0 ID:       ", args.post0_id)
    print("Post0 Timestamp:", edit0.timestamp)
    print("Post1 ID:       ", args.post1_id)
    print("Post1 Timestamp:", edit1.timestamp)
    print("Post2 ID:       ", args.post2_id)
    print("Post2 Timestamp:", edit2.timestamp)
    print("---")
    if result is not None:
        print(f"Annotation Timestamp ({LOCAL_TIMEZONE_NAME}):", datetime.astimezone(dateutil.parser.parse(result.timestamp), LOCAL_TIMEZONE))
        print("Annotation Response:", result)
    else:
        print(f"Annotation Timestamp ({LOCAL_TIMEZONE_NAME}):", "null")
        print("Annotation Response:", "null")

if __name__ == "__main__":

    parser  = ArgumentParser(argument_default=None)

    subparsers = parser.add_subparsers(required=True, dest="subcommand")
    single = subparsers.add_parser("single", help="annotate a single post")
    pair = subparsers.add_parser("pair", help="annotate a pair of posts")
    triple = subparsers.add_parser("triple", help="annotate a triple of posts")

    # single post annotation arguments
    single.add_argument("annotation")
    g0 = single.add_mutually_exclusive_group(required=True)
    g0.add_argument("--post_id")
    g0.add_argument("--post_file")
    # single.add_argument("--post_id", required=True)
    single.add_argument("--post_time", required=False)

    # pair post annotation arguments
    pair.add_argument("annotation")
    g0 = pair.add_mutually_exclusive_group(required=True)
    g0.add_argument("--post0_id")
    g0.add_argument("--post0_file")
    pair.add_argument("--post0_time", required=False)
    g1 = pair.add_mutually_exclusive_group(required=True)
    g1.add_argument("--post1_id")
    g1.add_argument("--post1_file")
    pair.add_argument("--post1_time", required=False)

    # triple post annotation arguments
    triple.add_argument("annotation")
    g0 = triple.add_mutually_exclusive_group(required=True)
    g0.add_argument("--post0_id")
    g0.add_argument("--post0_file")
    triple.add_argument("--post0_time", required=False)
    g1 = triple.add_mutually_exclusive_group(required=True)
    g1.add_argument("--post1_id")
    g1.add_argument("--post1_file")
    triple.add_argument("--post1_time", required=False)
    g2 = triple.add_mutually_exclusive_group(required=True)
    g2.add_argument("--post2_id")
    g2.add_argument("--post2_file")
    triple.add_argument("--post2_time", required=False)

    for subparser in [single, pair, triple]:
        subparser.add_argument("--no_read_from_cache", action="store_true")
        subparser.add_argument("--no_write_to_cache", action="store_true")
        subparser.add_argument("--only_cache", action="store_true")
        subparser.add_argument("--no_cache", action="store_true")
        subparser.add_argument("--logging_level", choices=["info", "warning", "error", "critical", "debug"], default="warning")
        subparser.add_argument("--args", nargs="*", action=ParseKwargs, default=dict())
        subparser.add_argument("--args_global", nargs="*", action=ParseKwargs, default=dict())
    args = parser.parse_args()

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    # quiet!
    moduel_root = logging.getLogger("annotation")
    if args.logging_level == "info":
        moduel_root.setLevel(logging.INFO)
    elif args.logging_level == "warning":
        moduel_root.setLevel(logging.WARNING)
    elif args.logging_level == "error":
        moduel_root.setLevel(logging.ERROR)
    elif args.logging_level == "critical":
        moduel_root.setLevel(logging.CRITICAL)
    elif args.logging_level == "debug":
        moduel_root.setLevel(logging.DEBUG)
    else:
        raise AssertionError()

    if args.subcommand == "single":
        run_single(args)
    elif args.subcommand == "pair":
        run_pair(args)
    elif args.subcommand == "triple":
        run_triple(args)
    else:
        raise ValueError(f"Unknown subcommad: {args.subcommand}")