# Docflow API Docs

This repository contains the Mintlify documentation for Docflow API.

## Languages

- Chinese: `docflow/cn`
- English: `docflow/en`
- Japanese: `docflow/ja`

Language navigation is configured in `docs.json` under `navigation.languages`.

### Development

Install the [Mintlify CLI](https://www.npmjs.com/package/mint) to preview the documentation changes locally. To install, use the following command

```
npm i -g mint
```

Run the following command at the root of your documentation (where docs.json is)

```
mint dev
```

If OpenAPI source files are changed, rebuild the bundled files before previewing:

```
openapi bundle docflow/cn/rest-api/openapi.yaml.src -o docflow/cn/rest-api/openapi.bundle.yaml
openapi bundle docflow/en/rest-api/openapi.yaml.src -o docflow/en/rest-api/openapi.bundle.yaml
openapi bundle docflow/ja/rest-api/openapi.yaml.src -o docflow/ja/rest-api/openapi.bundle.yaml
```

When adding or updating pages, keep `docflow/cn`, `docflow/en`, `docflow/ja`, and `docs.json` in sync.

### Publishing Changes

Install our Github App to auto propagate changes from your repo to your deployment. Changes will be deployed to production automatically after pushing to the default branch. Find the link to install on your dashboard.

#### Troubleshooting

- It the dev environment isn't running - Run `mint install` it'll re-install dependencies.
- Page loads as a 404 - Make sure you are running in a folder with `docs.json`
