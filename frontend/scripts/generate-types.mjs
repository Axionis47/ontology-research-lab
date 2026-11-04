import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { format } from "prettier";

const root = fileURLToPath(new URL("../../", import.meta.url));
const output = new URL("../src/api.generated.ts", import.meta.url);
const schema = process.env.OAK_OPENAPI_URL
  ? await (await fetch(process.env.OAK_OPENAPI_URL)).json()
  : JSON.parse(
      execFileSync(
        `${root}.venv/bin/python`,
        [
          "-c",
          "import json; from oak.api import create_app; print(json.dumps(create_app().openapi()))",
        ],
        { cwd: root, encoding: "utf8" },
      ),
    );
const source = await format(astToString(await openapiTS(schema)), {
  parser: "typescript",
});
if (process.argv.includes("--check")) {
  if (readFileSync(output, "utf8") !== source)
    throw new Error(
      "API types have changed. Run npm run types:generate and review the contract changes.",
    );
} else writeFileSync(output, source);
