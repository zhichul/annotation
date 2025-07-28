## `annotation`: Templated prompting and caching for LLM annotation of social media posts

### Overview

This is the `README` file for `annotation`. The package comes with a commandline interface  `annotate.py`. 

At a high level, `annotation` implements the following features in order to make developing multiple versions of prompts (for annotating social media posts) with a team of collaborators easier:
* `Templating`: You write a `.yaml` file with a templated prompt to call a LLM with, and our `annotation` fills in content such as the text of the post, its ancestors, and any other annotations. For example, you may include a LLM's `topic` annotation when prompting LLM about `relevance`. To see prompts written by our team check out `questions`.
* `Caching`: We store the results in a graph database (please specify a Jena endpoint using environment variable `RDF_URI`) so that unless otherwise specified, we use cached LLM calls to save cost.
* `Versioning`: We make sure that cache respects your local working tree - that is, if you made edits to `evidence_2_3.yaml` file that made it different from the `evidence_2_3.yaml` file that resulted in the cached result, we declare cache miss and run your version.

For a more detailed coneptual model see [CONCEPTUAL.md](CONCEPTUAL.md).

---
### Feature Highlights


#### Prompt Interpolation and Dependencies
Prompts are interpolated using `jinja2`. See examples in `question` folder. We provide pythonic references to `Post` and `Edit` so that you can use dotted syntax directly in your prompt template, importantly, they provides you access to attributes and function calling during interpolation to support the following usages:
* Post content and other static attributes (e.g. `"Below is the content of the post {{ post.content }} written at {{ post.timestamp }}"`)
* The annotation obtained by running another prompt on a set of post(s) (e.g. `"Here are the sentences where user makes claims: {{ post.claim(temperature=0) }}, do they agree with {{ post1.claim(temperature=0) }}?"`). 

Our engine will recursively execute any prompts dependended on first before interpolating their results into the referencing prompt.

For more on prompting syntax see [PROMPT.md](PROMPT.md).

#### Caching
We use a global LLM response cache (hosted as a Jena database) to support both scenarios below:

* prompt engineering with shared cache with collaborators
* running batch jobs that annoate tens of thousands social media posts, reusing prompt results when possible

Cache hit is determined based on version number match, as well as files hash matches of the entire dependency graph of prompts for an annotation in the working directory. This ensures that local prompt development can happen simultaneously across users without stepping on each other's cache, while also re-using annotations from stable prompts that could be shared between users. An additional side-benifit of having a cache is that it helps improve determinism, which is helpful for developing prompts that depend on one-another's outputs (nondeterminism with a graph of dependencies makes errors much harder to attribute.)

For additional details on cache schema see [JENA_SCHEMA.md](JENA_SCHEMA.md).

---
### Library Structure
Most of the prompt interpolation and cache hit detection is implemented in [anotation.py](annotation.py). 

Interactions with LLM is implemented in [llm_response.py](llm_response.py) and [llm_wrapper.py](llm_wrapper.py). 

Code in [cache.py](cache.py) provides interfacing with Jena databse endpoint. Other files include useful utilities and class definitions. 

Example prompts are under `questions/examples`, prompts we used in practice are under `questions/` directly.

---
For commandline usage see [USAGE.md](USAGE.md).
