
### YAML Syntax

One example of the YAML file `example_agreement_0_1.yaml` (the prompt itself is simple, but it uses many templates, and demonstrates the YAML format we support):

```yaml
---
args:
  model: "gpt-3.5-turbo-0125"
  temperature: 0.1 
  max_tokens: 1
  agreement_kw: "in agreement with"

alias:
  topic: "example_topic_0"
  relevance: "example_relevance_0"
  claim: "example_claim_0"
  has_claim: "example_has_claim_0"
---
{% if posts[0].relevance(post1) > 1 and post0.has_claim and post1.has_claim %}
method: openai
prompt:
  - system: "You are a helpful assistant."
  - user: |
      You will be given two social media posts. You should decide if the first post is {{agreement_kw}} the second. Please use a scale from 1 to 5, with 1 being not relevant and 5 being most relevant. Answer with a single number, do not give reasoning or explain it. Another LLM has also annotated the claims of those two posts.
      First post: '''{{ posts[0] }}'''\n\n
      LLM's annotation of its claim: {{ posts[0].claim }}
      Second post: '''{{ post1 }}'''
      LLM's annotation of its claim: {{ posts[1].claim }}
      Answer:

legal_answer_type:
  int

legal_answers:
  [1,2,3,4,5]

num_answers:
  1
{% else %}
method: static
value: Not applicable because either posts are not relevant enough or not making claims.
{% endif %}
```

The whole YAML file contains two sub YAML documents, separated by three dashes `---`:
* The first document contains declared arguments, which can be overidden 
    1) at the command line or 
    2) by another yaml file that depends on the annotation of this yaml file
* The second document contains prompt templates and additional prompting arguments, these cannot not be overridden. If attempted to override, a warning will be thrown but the code will run simply ignoring the attempted override. 

The first file has the following fields:

* `args`: These `args` will be passed down to 
    1. the iterpolation of templates in the second YAML document.
    2. the LLM call, including but not limited to `model`, `temperature`, and  `max_tokens`.
    This list of arguments is treated as declared overridable.
* `alias`: any names as well as attributes introduced with a dotted syntax in the template (the second yaml document) will be replaced by `alias[name]` if the name or attribute is in the alias list. For example, with the alias list above, we can simply write `posts[0].topic` instead of the fullname `example_topic_0_1`. This alias is local to the YAML file.

The second sub YAML file contains the following fields:
* `method`: `method` should be one of `openai`, `vllm`, or `static`. The former two correspond to two ways of annotation, using OpenAI API models or open-source vLLM servers. `static` means that this prompt will not proceed to LLM to annotate, and returns the `value` field (currently just echos back `static`).
#### For `method: openai` or `method: vllm` or `method: human`
`prompt`: `prompt` is a list of prompts with roles. The first should start with `system` and following prompts should alternate between `user` and `assistant`. Each role should start with a dash (`-`) since dash signals a YAML list.

Here's a list of optional arguments:
* `legal_answer_type`: `legal_answer_type` should be a str corresponding to `int`, `float`, `str`, and `json`. Notice these should also be explicitly stated in the prompt.
* `legal_answers`: `legal_answers` is a list indicating all legal answers. If `null`, we will not perform any filtering.
* `num_answers`: The number of answers you want from LLMs. Must be an integer.

You can also specify any of the `model`, `temperature`, and `max_tokens` here, but it would get overidden by `args` (so there's no point in specifying them in both). If not declared in `args` but declared here in the second document, then they'll not be possible to override.

If `method: human` you will be shown the prompts at the command line and asked to provide answer in one line (hit enter to submit).

#### For `method: static` 
`value` field specifies the returned value. It will be a `str`.

#### Additional Jinja syntax, and our default names
* See jinja2 documentation https://jinja.palletsprojects.com/en/3.1.x/templates/.

* There are three kinds of default objects declared implicitly to refer to posts. `posts` is a list that you can index using python syntax. `post{i}` such as `post0` is a shorthand for that. `post` by default resolves to `post0`.

* You can refer to names defined in `args`, in the example above, `agreement_kw` was declared and thus usable in template filling.

* `post.xx` would resolve first to defined attributes / method on the python object so be mindful when naming your annotations so it doesn't get shadowed. Currently here's the list:
    - `status()`
    - `history()`
    - `context()`
    - `latest()`
    - `is_loaded()`
    - `content` (a cleaned up version of the mastodon json value)
    - `content_raw` (the mastodon json value)
    - `data` (the entire mastodon json)
    - `mastodon_id`
    - `parent`
    - `ancestors`
    - `sha256`
    
    If `xx` is not a defined attribute. Then it would attept to resolve to a annotation such as `evidence_0_1` if you wrote `post.evidence_0_1`, and if that fails, finally it trys to resolve it as a key from the json returned by mastodon status api (e.g. `created_at` field). We introduced a `timestamp` field to disambiguously represent the time the `Edit` was written (mastodon uses a combination of `created_at` and `edited_at` which is confusing).
