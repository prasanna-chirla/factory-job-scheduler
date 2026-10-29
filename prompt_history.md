# AI Use and Prompting History

## AI tool used

I used **OpenAI Codex in the Codex desktop app only** for AI assistance on this project. I did not use other AI tools. AI responses are not reproduced here; this file describes how I used Codex and what I reviewed.

## Prompt history: how my requests developed

My prompts became more specific as I learned the assignment. I shared the project brief, then used follow-up questions and actual run results to focus each next step. The sequence was:

1. **Start from the assignment brief.** I shared the manufacturing scheduling problem and its requirements. This established the context for the later questions about project structure, implementation, running the program, and understanding the results.
2. **Make the project understandable.** I asked for a clear folder structure and later asked what the problem, solution, inputs, and outputs meant. These prompts helped me connect the assignment language to the project's files and modules.
3. **Get the program running.** I asked how to run the project with `uv`, then pasted the actual Python traceback when the schedule validator failed. I asked how I could test the application myself and what the fixed seed meant.
4. **Check the implementation against the requirements.** I shared the assignment text again and asked whether the code covered it, then asked for additional requested items to be implemented. This focused Codex on requirement coverage rather than only producing code that ran.
5. **Learn by reducing the dataset.** I asked for a simple input and used command-line parameters to run a small case: 4 SKUs, 4 machines, 1 order, 8 materials, and a fixed seed. That made the generated CSVs small enough to inspect.
6. **Investigate a specific validation result.** When the one-order run reported a ground-truth failure, I shared the result and asked why. After learning that the changeover case needed different product families, I challenged whether a one-product schedule should fail. I then asked Codex to change unsupported edge-case checks to `NOT_APPLICABLE` instead of treating them as schedule failures.
7. **Make repeated runs easier to understand.** I asked what happens to old generated files, considered whether they should be deleted or replaced, and then explicitly requested a cleanup feature. This prompted the generator to clear its old generated data before writing the new run.
8. **Prepare the submission.** I asked what to push to GitHub, how to authenticate for the target repository, and what to include in the repository description and commit message. I also shared the submission PDFs and asked Codex to compare their requirements with the project.

This sequence shows how I used prompts to move from a broad requirement to implementation, then to error-driven debugging, small-scale learning, and submission checks. The descriptions above summarize my requests; they are not a verbatim copy of every message in the Codex conversation.

## How I used AI during development

I worked through the assignment in stages instead of asking for one large, unexplained result:

1. **Understand the assignment.** I provided the business brief and asked for plain-language explanations of the problem, inputs, outputs, and relationships between the factory data files.
2. **Build the solution in parts.** I asked for a structured Python project that generates synthetic products, routings, machines, shifts, orders, materials, and inventory, then schedules the work and reports the results.
3. **Diagnose real run errors.** When I ran the program and received a Python traceback or a failed validation status, I shared the output. The AI traced the issue to the relevant validator or test-case construction and explained the reason before changing the code.
4. **Use a small, reproducible run to learn the flow.** I ran the program with four SKUs, four machines, one order, eight materials, and a fixed seed. I inspected the resulting CSV and JSON files and asked how the records connect.
5. **Review edge-case behavior.** The one-order run exposed a ground-truth changeover test that could not be constructed because the schedule had no switch between product families. I questioned whether a valid one-product schedule should fail. The AI updated the evaluator so unsupported scenarios are marked `NOT_APPLICABLE`; applicable checks still need to pass for validation to pass.
6. **Document the project.** I asked for clear run instructions, explanations of the data folders, and submission guidance so I could understand and present the work.

## Where AI helped most

AI accelerated the initial project structure, implementation of the data generator, scheduler, validators, metrics, and reporting, and diagnosis of run-time and small-dataset edge cases. It also helped translate technical output into explanations I could follow.

The implementation was substantially AI-assisted. I used AI output as a draft, ran the application locally, reported the actual results, asked follow-up questions when behavior was unclear, and requested changes when the result did not match the assignment's intent. I did not treat a generated explanation or a passing report as a substitute for understanding the code.

## What I ran and reviewed

- I ran the small configuration from PowerShell:

  ```powershell
  uv run main.py --out . --skus 4 --machines 4 --orders 1 --materials 8 --seed 20261022
  ```

- I reviewed the generated production order, its four order operations, material requirements and reservations, four scheduled operations, metrics, validation report, and ground-truth evaluation.
- The small run reported overall validation `PASS`. Four applicable ground-truth scenarios passed; the changeover-omission scenario was `NOT_APPLICABLE` because a single product family created no changeover to omit.
- The unit-test suite passed during an earlier development stage. It was not rerun after the final small-dataset ground-truth and generated-file cleanup changes, so those final edits still need a fresh test-suite run before submission.

## My review and remaining checks

I reviewed the run outputs and asked for explanations of the data relationships, validation behavior, and limitations. Before submitting, I will run the current test suite, inspect the final full-size run and reports, and make sure I can explain the scheduler's decisions and known limitations.

## Prompt transcript completeness

This file includes a chronological summary of how I prompted Codex, not a verbatim transcript of every prompt. Since Codex was the only AI tool I used, there are no other AI-tool prompts to include.
