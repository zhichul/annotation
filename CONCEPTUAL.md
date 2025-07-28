
### Conceptual Model

We identify a social media post `Post` with its mastodon id. We identify an `Edit` by its mastodon id **and** a timestamp.

The templated `Prompt`s are to be included in `.yaml` files under the `PROMPT_FOLDER` environment variable directory or any of its nested subdirectories.
> By default, you should set `PROMPT_FOLDER` to `annotation/questions`.

 These `.yaml` files also contain several other useful information such as declaring a list of additional `Arguments`, that can be overwritten at the commandline, or by another `.yaml` prompt that references it.
 > For example, `example_quality_0_1.yaml` depends on `example_evidence_0_1.yaml`, and specifies that it wants to use `example_evidence_0_1` generated at temperature 0 instead of whatever default temperature speicified in `example_evidence_0_1.yaml`. We will explain how these `.yaml` files are structured later in the README. We refer to a particular `.yaml` file as a `Question`, because it's a question that we will ask a LLM or a human.

 Given a `Question`, its `Arguments`, and the `Post`s being annotated, our library will call the LLM (or ask a human,or just execute some code), and obtain a `Response`. A `Response` may have many `Items` (think sampling `n` times from a LLM producing a list of `n` items). We call the tuple of `Question`, `Arguments`, `Post`s, and the `Response` an `Annotation`. An `Annotation` is also timestamped, and is signed by default by the currently logged in username (e.g. `blu` for Brian's PC). 

In sum, here's the list of concepts involved in using the package:
* Posts: `Post`, `Edit`, 
* Prompts: `Question`, `Prompt`, `Arguments`
* Results: `Response`, `Annotation`.
---