### Commandline Usage

First, configure `.env` as described in `README.md` in the root directory of this repo.  The commands below assume that your working directory is project root (which contains the `annotate` script).

The commandline interface currently supports annotations of a single posts, a pair of posts, or a triplet of posts.

##### ./annotate.py single
<details>
<summary> Expand </summary>

Arg list:
  * `annotation`: This is a required positional argument specifiying the name of the annotation you want to compute. Name should be one of the `.yaml` files in the directory corresponding to the `PROMPT_FOLDER` environment or its subdirectories (defined above). Names are required to be formatted as `{name}_{major}_{minor}`, where `name` is allowed to contain any symbol that your os allows to be in filenames, as long as the `major` and `minor` version numbers are included at the end. Example: `example_quality_0_1`.
  * `--post_id`: this is the mastodon id of the post, required, but provided as a named argument
  * `--post_file`: this is mutually exclusive with `--post_id`, specify a path to a plain text file to annotate. `--post_time` is ignored when `--post_file` is set.
  * `--post_time`: this is the timestamp of the post, specify this to select an edit of the post that is not the latest edit (if `post_time` not supplied it is by default the latest).
  * `--no_read_from_cache`: if set, never use cached results in this run.
  * `--no_write_to_cache`: if set, never write to cache in this run.
  * `--args k=v`: override a list of declared arguments (described in YAML syntax section) for this annotation only 
  * `--args_global k=v`: override a list declared arguments for any recursive annotations
  * `--post_file`

`--args` takes precedence over `--args_global`. So if you say `--args method=openai` and `--args_global method=human`, it will run any dependenceies with `method=human` but the top level annotation specified by `anntation` with `method=openai`.
</details>


##### ./annotate.py pair
<details>
<summary>Expand</summary>

Arg list same as pair except for providing the two post ids and timestamps:
* `--post0_id`, `--post0_time`: id and timestamp for the post being annotated
* `--post1_id`, `--post1_time`: id and timestamps for the anchor post

Otherwise all arguments inherited from `single` mode.
</details>

##### ./annotate.py triple
<details>
<summary>Expand</summary>

Same as pair except for `--post2_id/time`.
</details>

#### Examples

Simple prompt examples to demonstrate functionality are included in `questions/example`. See prompts directly under `questions` for prompts actually used to annotate social media posts.

<details>
<summary>Examples</summary>

Example single post annotation:

```
./annotate single example_quality_0_2 --post_id 112718194195663750 --post_time 2024-07-02T17:59:08.737Z --no_read_from_cache --no_write_to_cache
```
Expected Output:
```
---
Question: example_quality_0_2
Post: 112718194195663750
Post Timestamp: 2024-07-02T17:59:08.737Z
---
Annotation Timestamp: currently not supported
Annotation Response: 0
```

Example pair post annotation:

```
./annotate pair example_agreement_0_1 --post0_id 112718194195663750 --post0_time 2024-07-02T17:59:08.737Z --post1_id 112718098683258328 --post1_time 2024-07-02T17:40:36.098Z --no_read_from_cache --no_write_to_cache
```
Expected Output:
```
---
Question: example_agreement_0_1
Post0: 112718194195663750
Post0 Timestamp: 2024-07-02T17:59:08.737Z
Post1: 112718194195663750
Post1 Timestamp: 2024-07-02T17:59:08.737Z
---
Annotation Timestamp: currently not supported
Annotation Response: Not applicable because either posts are not relevant enough or not making claims.
```

Example triple annotation:
```
poetry run python3 -m pdb -c continue annotate.py triple example_similarity_anchored_0_1 --post0_id 112718194195663750 --post2_id 112718194195663750 --post1_id  112731161349619740 --no_write_to_cache --no_read_from_cache
```

Expected Output:
```
---
Question:        example_similarity_anchored_0_1
Post0 ID:        112718194195663750
Post0 Timestamp: 2024-07-02T18:27:24.518Z
Post1 ID:        112731161349619740
Post1 Timestamp: 2024-07-05T00:56:50.000Z
Post2 ID:        112718194195663750
Post2 Timestamp: 2024-07-02T18:27:24.518Z
---
Annotation Timestamp (US/Eastern): 2024-07-08 17:43:28.143890-04:00
Annotation Response: 0
```

Example override to run dependencies in human mode but (for some reason) run top-level annotation with openai:
```
poetry run python3 -m pdb -c continue annotate.py single example_maybe_human_claim_0_1 --post_id 112718194195663750 --no_read_from_cache --no_write_to_cache --args temperature=0.0 --args_global method=human --args method=openai
```

Expected Output:
```
INFO:root:Resolved .example_maybe_human_has_claim_0_1 to <annotation.annotation.BoundAnnotation object at 0x7f61adbaded0>
[
  {
    "role": "system",
    "content": "You are a helpful assistant."
  },
  {
    "role": "user",
    "content": " You will be given social media posts. You should judge whether the post has a claim. Give your answer as 0 or 1, where 0 means no claim, and 1 means has claims. Post: ''' @yuki622 And now I don&#39;t (edited 4) ''' Answer: "
  }
]
Enter your annotation result: 1
---
Question:       example_maybe_human_claim_0_1
Post ID:        112718194195663750
Post Timestamp: 2024-07-02T18:27:24.518Z
---
Annotation Timestamp (US/Eastern): 2024-07-08 19:15:12.172307-04:00
Annotation Response: Claim: Expressing a change in feelings or behavior.
```

Example post from file (post from file is identified by content instead of id+timestamp):

```
poetry run python3 -m pdb -c continue annotate.py single example_maybe_human_claim_0_1 --post_file src/curate/annotation/posts/example.txt --args_global method=human
```
This would load my cached anntoation below:
```
---
Question:       example_maybe_human_claim_0_1
Post ID:        None
Post Timestamp: 2000-01-01 00:00:00
---
Annotation Timestamp (US/Eastern): 2024-07-08 19:42:43.949130-04:00
Annotation Response: 1
```
You can ignore this cache if you put `--no_read_from_cache`, which would prompt you to write your human annotation and cache it in the database as well.
</details>

#### Advanced usage
By default, if neither of the `no_read_from_cache` or `no_write_to_cache` flags are set, the library looks for any cached results, and inserts it if it does not exist. Future calls will then return the cached version by default. If you would like to add another entry to the cache with the same version of `Question` and same arguments (e.g., just run the LLM again to see if the result changes due to nondeterminism), then you can set the `no_read_from_cache` flag. If you want to not use cached result and also not write the new entry to the cache, then also set `no_write_to_cache`.
