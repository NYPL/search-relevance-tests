# Search Relevance Tests

This script generates ElasticSaerch performance/relevancy reports for configured applications.

## Testing an application

To test an application's search performance and relevance, establish a directory in `./applications/` (e.g. `./applications/discovery-api`).

The application folder should contain the following files:

`commits.csv`: A CSV, with header, that defines:
 - `commit`: The git commit hash
 - `description`: A friendly description for the significant change(s) 

`targets.yaml`: A YAML file with multiple documents defining:
 - `params`: A hash of the query params recognized by the application (e.g. `q`, `isbn`, `search_scope`, etc.)
 - `metric`: The rank-eval metric (e.g. "precision", "recall")
 - `metric_at`: The rank-eval metric-at param
 - `relevant`: The set of ids constituting "good" hits
 - `notes`: An array of notes explaning the premise, origin, expectations of the target.

More TK
