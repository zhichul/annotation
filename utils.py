import copy
import functools
import hashlib
import json
import os
import re
from typing import Any
import jinja2
import jinja2.nodes
from annotation import constants
import logging
import subprocess

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def sparql_dumps(s):
    if not isinstance(s, str):
        s = str(s)
    return json.dumps(s)

def sparql_loads(s):
    if not isinstance(s, str):
        s = str(s)
    return json.loads(s)

def escape_single_quote(s):
    if s.startswith("'"):
        s = r"\'" + s[1:]
    if s.endswith("'"):
        s = s[:-1] + r"\'"
    return s 

def escape_first_last_double_quote(s):
    if s.startswith('"'):
        s = r"\"" + s[1:]
    if s.endswith('"'):
        s = s[:-1] + r"\""
    return s 

@functools.cache
def sha256_hash_by_lines(*docs : str) -> str:
    sha256_hash = hashlib.sha256()
    for document in docs:
        for line in document.splitlines():
            sha256_hash.update(line.encode('utf-8'))
    return sha256_hash.hexdigest()

def get_all_files(top):
    out = []
    for dir, _, files in os.walk(top):
        for file in files:
            out.append(os.path.join(dir, file))
    return out

def escape_double_quotes(s):
    return s
    # return json.dumps(s)[1:-1] # s.replace('"', r'\"')

def escape_escaped_double_quotes(s):
    return s.replace(r'\"', r'\\\"')

def unescape_escaped_double_quotes(s):
    return s.replace(r'\\\"', r'\"')

def escape_double_quotes_decorator(f):
    # def g(*args, **kwargs):
    #     s = f(*args, **kwargs)
    #     return json.dumps(s)[1:-1] # s.replace('"', r'\"')
    def g(*args, **kwargs):
        return f(*args, **kwargs)
    return g

def clean(content:str):
    cleaned_content = re.sub('\\u003C.*?\\u003E', ' ', content)
    cleaned_content = re.sub('( )+', ' ', cleaned_content)
    return cleaned_content

def render_with_alias(env, template, alias, **kwargs):
    ast = env.parse(template)
    substitute_aliases(ast, alias)
    rendered_string = env.from_string(ast).render(**kwargs)
    return rendered_string

def substitute_aliases(template: jinja2.nodes.Template, aliases: dict[Any, Any]):
    for node in template.find_all(jinja2.nodes.Getattr):
        if node.attr in aliases:
            node.attr = aliases[node.attr]
    for node in template.find_all(jinja2.nodes.Name):
        if node.name in aliases:
            node.name = aliases[node.name]
    return template

def nested_copy_dict(old: dict[Any, Any]):
    return {k:nested_copy_dict(v) if isinstance(v, dict) else v for k,v in old.items()}

def nested_update_dict(old: dict[Any, Any], new: dict[Any, Any], allow_new=False, strict=False):
    """
    Overrides existing values of keys in old with values in new.
    Throws exception by default if new accidentally contains new keys.
    Throws exception if new has value that type mismatch with old.

    Importantly, only takes values from new, does not alias subdicts.
    """
    for key in old.keys() | new.keys():
        if key in new and key not in old:
            if allow_new:
                old[key] = copy.deepcopy(new[key])
            else:
                if strict:
                    raise ValueError(f"{key} not in old but in new. nested update only allows updating values of dict,"
                                    " but does not allow adding new keys.")
                else:
                    logger.warning(f"Ignoring {key} since allow_new is set to False and {key} not in old.")
                    continue

        if key in old and key in new:
            if type(old[key]) != type(new[key]):
                raise ValueError(f"type mismatch: old {type(old[key])} new {type(new[key])}")
            if isinstance(old[key], dict):
                nested_update_dict(old[key], new[key], allow_new)
            else:
                old[key] = new[key]

def split_yaml_docs(s: str):
    return s.split("\n---")

def overload_ops(cls, coersion):
    def override_first(operator):
        def g(*arguments):
            return getattr(coersion(arguments[0]), operator)(*arguments[1:])
        return g
    for op in constants.OP_OVERRIDES:
        setattr(cls, op, override_first(op))

def pretty_print_human(messages):
    try:
        print("---")
        for message in messages:
            print(f"role: {message['role']}")
            print(f"content: {message['content']}")
            print("---")
    except Exception as e:
        print(json.dumps(messages, indent=2))


def get_git_revision_hash() -> str:
    """
    https://stackoverflow.com/questions/14989858/get-the-current-git-hash-in-a-python-script
    """
    return subprocess.check_output(f'cd {os.path.dirname(__file__)}; git rev-parse HEAD', shell=True, executable="/bin/bash").decode('ascii').strip()

def get_git_branch() -> str:
    return subprocess.check_output(f'cd {os.path.dirname(__file__)}; git rev-parse --abbrev-ref HEAD', shell=True, executable="/bin/bash").decode('ascii').strip()


class Quest:

    def __init__(self, name=None, major=None, minor=None, sha256=None):
        self.children = []
        self.dependencies = [] # concatenation of recursively flattened childs
        self.name = name
        self.major = major
        self.minor = minor
        self.sha256 = sha256
    
    def __hash__(self) -> int:
        return hash((self.name, self.major, self.minor, self.sha256))
    
    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Quest):
            return False
        return o.major == self.major and o.minor == self.minor and o.name == self.name and o.sha256 == self.sha256

class CallStack:

    def __init__(self) -> None:
        self.tree = None
        self.stack = []
    
    def enter(self, **kwargs):
        new_node = Quest(**kwargs)
        # grow the tree
        if self.tree is None:
            self.tree = new_node
        else:
            self.stack[-1].children.append(new_node)
        # update stack
        self.stack.append(new_node)
        return self.current
    
    def exit(self):
        out = self.stack.pop()
        if len(self.stack) == 0:
            # last exit call will reset all states
            self.tree = None
            self.stack = []
        else:
            # add dependencies of current node of the returning call
            self.current.dependencies.extend([out, *out.dependencies])
        return out

    @property
    def current(self):
        if len(self.stack) == 0:
            raise ValueError()
        return self.stack[-1]
    
