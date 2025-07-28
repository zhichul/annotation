import datetime
import functools
import dateutil
import dateutil.parser
import requests
from annotation import api_context_states, utils
import threading
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class RecordNotFoundError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def request_json(url):
    r = requests.get(url)
    
    json_data = r.json()
    
    if "error" in json_data and json_data["error"] == "Record not found":
        raise RecordNotFoundError(f"Record not found at {url}")
    
    r.raise_for_status()
    return r.json()

class PostList(list):

    def __str__(self):
        return self.content
    
    def __getattr__(self, name):
        return "\\n\\n".join([str(getattr(p, name)) for p in self])

class Post:
    """
    This is the class for a mastodon post, without a timestamp.
    """
    
    history_url_format = "{0}/v1/statuses/{1}/history"
    context_url_format = "{0}/v1/statuses/{1}/context"
    status_url_format = "{0}/v1/statuses/{1}"

    def __init__(self, mastodon_id: str):
        self._mastodon_id = mastodon_id

    def __repr__(self):
        return f"Post({self._mastodon_id})"

    def status(self) -> dict:
        return request_json(self.status_url_format.format(api_context_states.get_mastodon_url(),
                                                          self._mastodon_id))

    def history(self) -> dict:
        return request_json(self.history_url_format.format(api_context_states.get_mastodon_url(),
                                                           self._mastodon_id))
        
    def context(self) -> dict:
        return request_json(self.context_url_format.format(api_context_states.get_mastodon_url(),
                                                           self._mastodon_id))

    def latest(self, cutoff: datetime.datetime | None = None):
        # find the latest edit before cutoff
        edits = self.history()
        if cutoff is not None:
            edits = list(filter(lambda x: dateutil.parser.parse(x["created_at"]) <= cutoff, edits))
            if len(edits) == 0:
                raise ValueError(f"No edits of {self._mastodon_id} before {cutoff}")
        latest_edit = edits[-1] # assumes mastodon history returns in ascending order of time         
        latest_timestamp =  dateutil.parser.parse(latest_edit["created_at"])

        # construct the python object for that edit
        return Edit.new(self._mastodon_id, latest_timestamp) # this could be a cached object

class EditFromStr:
    
    def __init__(self, str) -> None:
        self.str = str

    def __getattr__(self, name):
        if api_context_states.is_supported_annotation(name):
            from annotation import annotation
            bound_f =  annotation.BoundAnnotation(api_context_states.get_supported_annotation(name), self)
            logger.info(f"Resolved .{name} to {repr(bound_f)}")
            return bound_f
        raise AttributeError(f"{name}")

    def __repr__(self):
        return f"EditFromStr({self.str})"

    def __str__(self):
        return self.content

    @property
    @utils.escape_double_quotes_decorator
    def content(self):
        return self.str

    @property
    def mastodon_id(self):
        return "0"
    
    @property
    def timestamp(self):
        return "2000-01-01 00:00:00"
    
    @property
    def sha256(self):
        return utils.sha256_hash_by_lines(self.content) # type:ignore

    def __hash__(self) -> int:
        return hash(self.sha256)

    def __eq__(self, o) -> bool:
        return isinstance(o, EditFromStr) and self.content == o.content

class EditFromFile(EditFromStr):
    
    def __init__(self, file) -> None:
        with open(file, "rt") as f:
            super().__init__(f.read())
        self.file = file

    def __repr__(self):
        return f"EditFromFile({self.file})"

    def __str__(self):
        return self.content

class Edit(Post):

    def __init__(self, mastodon_id: str, timestamp: datetime.datetime):
        """
        If you want Edit objects to be cached so that you don't keep calling
        mastodon api, use Edit.new to create new Edit object.

        A concrete Edit need an id and a timestamp. If timestamp is not specified use 
        Post instead.
        """
        # id and timestamp uniquely identify a post
        super().__init__(mastodon_id)
        self._timestamp = timestamp
        self.lock = threading.RLock()

        # lazily load self
        self._data = None
        self._parent = None
        self._parent_is_set = False
        self._ancestors = None
        self._cleaned_content = None

    @property
    def is_loaded(self):
        return self._data is not None

    @property
    @utils.escape_double_quotes_decorator
    def content(self):
        if self._cleaned_content is None:
            self._cleaned_content = utils.clean(self.content_raw)
        return self._cleaned_content

    @property
    def content_raw(self):
        return self.data["content"] # type:ignore

    @property
    def parent(self):
        with self.lock:
            if not self._parent_is_set:
                if self.data["in_reply_to_id"] is not None: # type:ignore
                    self._parent = Post(self.data["in_reply_to_id"]).latest(cutoff=self._timestamp) # type:ignore
                self._parent_is_set = True
            return self._parent

    @property
    def ancestors(self):
        with self.lock:
            if self._ancestors is None:
                self._ancestors = PostList()
                for ancestor in self.context()["ancestors"]:
                    self._ancestors.append(Post(ancestor["id"]).latest(cutoff=self._timestamp))
            return self._ancestors

    @functools.cache
    @staticmethod
    def new(mastodon_id: str, timestamp: datetime.datetime):
        """
        This guarantees within each process, every id+time combination (an edit)
        is only represented once, and thus only loaded once.
        """
        edit = Edit(mastodon_id, timestamp)
        return edit

    @property
    def data(self) -> dict:
        with self.lock:
            if not self.is_loaded:
                # fetch metadata (including content of latest edit)
                self._data = self.status()
                # fetch history and find edit matching timestamp
                history = self.history()
                match = None
                for edit in history:
                    edit_timestamp = dateutil.parser.parse(edit["created_at"])
                    if edit_timestamp == self._timestamp:
                        match = edit
                        break
                if match is None:
                    raise ValueError(f"No post found with id {self._mastodon_id} at timestamp {self._timestamp}")
                timestamp = match["created_at"]
                del match["created_at"]
                match["timestamp"] = timestamp
                self._data.update(match)
            return self._data # type:ignore
    
    def __getattr__(self, name):
        if api_context_states.is_supported_annotation(name):
            from annotation import annotation
            bound_f =  annotation.BoundAnnotation(api_context_states.get_supported_annotation(name), self)
            logger.info(f"Resolved .{name} to {repr(bound_f)}")
            return bound_f
        if name in self.data:
            s = self.data[name] # type:ignore
            if isinstance(s, str):
                return utils.escape_double_quotes(s)
        raise AttributeError(f"{name}")

    def __repr__(self):
        return f"Edit({self._mastodon_id}, {self._timestamp.__repr__()})"

    def __str__(self):
        return self.content
    
    @property
    def mastodon_id(self):
        return self._mastodon_id
    
    @property
    def sha256(self):
        # TODO: this can result in uri collisions even though chances are low
        return utils.sha256_hash_by_lines(self.mastodon_id, self.timestamp, self.content) # type:ignore

    def __hash__(self) -> int:
        return hash(self.sha256)

    def __eq__(self, o) -> bool:
        return isinstance(o, Edit) and self.mastodon_id == o.mastodon_id and self.timestamp == o.timestamp and self.content == o.content

if __name__ == "__main__":
    from jinja2 import Environment
    post = Post("112718194195663750")
    x = post.latest()
    y = post.latest()
    z = post.latest(cutoff=dateutil.parser.parse("2024-07-02T17:59:29.036Z"))
    assert x is y
    assert x is not z
    print("x is the latest version, when we get parent, we get the latest parent before x's timestamp")
    print("x       :", x.mastodon_id, x.content, x.timestamp)
    print("x.parent:", x.parent.mastodon_id, x.parent, x.parent.timestamp) # type:ignore
    print("z is an earlier edit, when we get parent, we get the latest parent before z's timestamp")
    print("z       :", z.mastodon_id, z.content, z.timestamp)
    print("z.parent:", z.parent.mastodon_id, z.parent, z.parent.timestamp) # type:ignore
    print("Observe that the ids of x/z and x.parent/z.parent are the same.")
    print("x.ancestors:", repr(str(x.ancestors)))
    print("z.ancestors:", repr(str(x.ancestors)))

    env = Environment()
    print(api_context_states.supported_annotations["humor_0_0"]["object"](x)) # type:ignore
    print(env.from_string(utils.substitute_aliases(env.parse("Here's a jinja2 template that uses humor: {{ post.humor }}"), {"humor": "humor_0_0"})).render(post=x))