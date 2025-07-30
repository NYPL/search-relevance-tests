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

`initialize.sh`: A BASH script that initializes the app at the specified location (e.g. using `git`) and install dependencies. The script expects two arguments:
 - `BASEDIR`: The location on disk to initialize the application.
 - `COMMIT`: The git commit hash to check out

`get-config.sh`: A BASH script that accepts two arguments:
 - `BASEDIR`: The location of the app on disk.
 - `OUTFILE`: The location that the script should write the config to. (e.g. `/tmp/config.json`). This outfile is expected to ultimately be a JSON that defines:
   - `nodes`: ES host(s)
   - `apiKey`: ES api-key
   - `index`: ES index

`get-query.sh`: A BASH script that accepts three arguments:
 - `BASEDIR`: The location of teh app on disk.
 - `INFILE`: The location of a JSON file on disk defining the query. (e.g. `/tmp/query-params.json`)
 - `OUTFILE': The location on disk that the script should write the application-generated ES query (e.g. `/tmp/es-query.json`)

## Setup

To install all dependencies and activate a venv:
```
make venv
source .venv/bin/activate
```

## Running

```
make venv
source .venv/bin/activate
```

To re-run all tests against all registered commits for a named application (for example when targets are modified):
```
python main.py APPLICATION all [--rows ROWS]
```

To run tests for a named, local application (for example to assess changes under development):
```
python main.py APPLICATION current [--rows ROWS] [--appdir APPDIR]
```

To rebuild the report for a named application using saved manifests:
```
python main.py APPLICATION rebuild-report
```

### Docker:

To build a local image for local invocation:
```
docker build . -t search-relevance-tests --target local
```

You can then run arbitrary commands:
```
docker run -it -v $HOME/.aws/credentials:/root/.aws/credentials:ro search-relevance-tests APP COMMAND [--options...]
```

### Sam:

To run the function in a simulated Lambda environment locally:

```
sam build -t sam.template.yml
sam local invoke -t .aws-sam/build/template.yaml SearchRelevanceTests -e events/...
```

## Deployment

Deployment is handled by GHA on merge to `main`. These steps include:
 - `./provisioning/push-image.sh`
 - `terraform -chdir=provisioning init`
 - `terraform -chdir=provisioning apply -var 'environment=qa'`
