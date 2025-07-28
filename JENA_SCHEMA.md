
### Querying Jena to check your cached annotations
Example:
```
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX post: <post#>
PREFIX annot: <annotation#>
PREFIX quest: <question#>
PREFIX resp: <response#>
PREFIX item: <response_item#>


SELECT ?auth ?resp ?item ?k ?v WHERE {
  ?post post:id "112731161349619740" .
  ?annot annot:post0 ?post .
  ?annot annot:timestamp ?time .
  ?annot annot:run_by ?auth .
  ?annot annot:resp ?resp .
  ?resp resp:item ?item .
  ?item ?k ?v .
} LIMIT 100
```
Enter this at `http://your_rdf_uri:3030/#/dataset/your_cache_name/query`.

For pairwise annotations, use `annot:post0` and `annot:post1`.

### Jena schema

```
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX post: <post#>
PREFIX annot: <annotation#>
PREFIX quest: <question#>
PREFIX resp: <response#>
PREFIX item: <response_item#>
```

Every `annot:{id}` has attributes `annot:timestamp`, `annot:response`, `annot:git_branch`, `annot:run_by`, `annot:git_commit`, `annot:git_hash`, `annot:hash`, `annot:quest`, `annot:resp`, and `annot:post{i}`.

Every `post:{id}` has attributes `post:timestamp`, `post:content`, and `post:id` (mastodon id). The id is the hash of the tuple (mastodon id, timestamp, content).



