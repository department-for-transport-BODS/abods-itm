# Getting Started

You can use https://mise.jdx.dev/ as a tool manager and task runner.
If that is installed and on your PATH, you should be able to run `mise install` to install required tools.

> [!NOTE]
> If you don't wish to use mise, check the versions of tools in [mise.toml](../mise.toml)/[.tool-versions](../.tool-versions) and install matching versions.
> `.tool-versions` is used to provide compatiblity with asdf.
> 
> The rest of the guide will assume usage of that tool, but you can check [mise.toml](../mise.toml) to find the commands to run.

Run `mise tasks` to get a list of tasks you can run.
Many tasks use [Granted](https://docs.commonfate.io/granted/getting-started), and its `assume` command for convenience when working across multiple AWS accounts.
You may also wish to manage this differently.

You may wish to set up your editor of choice to use a venv, and use that from your terminal at this point.

`mise r install` will install the requirements at [requirements.txt](../ingestion_pipelines/requirements.txt), needed for local development.

## Connecting to a database

You can connect to the database using the mise tasks starting with `db`, or use the [db-connect.sh](../scripts/db-connect.sh) script directly.

Then you can log in to the database on `localhost:15432`, database:abods, using provided credentials.
If you have the right access to the AWS environment, you can use credentials for the `abods_proxy_rw` user, 
as this is what runs migrations in most environments (sandbox is manual changes only :( ).

If your DB client supports it, set the connection to read-only whenever possible.

## Contributing

Standard, make a branch, push it, open a PR, get it reviewed, then merge it. 
See [Deployment](./Deployment.md) for more info on deploying code.  

Use squash-and-merge for a clean history.

Most of the work is likely to be in the matching logic.

You can use the `mise r example` task to generate a new test case from historic data in the sandbox database 
(easily adapted for other environments if needed).
This will generate new test data and assertions that will run in CI if you choose to commit and push.
Or you can just use this to check what try the logic locally and discard the output.
The example generated will not be correctly formatted, and will fail linting until you add a description to the test file.

You may need to recreate existing examples when the matching logic changes, but this may highlight issues with the logic.
There are also manually created unit tests that will catch regressions.
