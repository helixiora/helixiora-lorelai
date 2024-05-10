# Benchmarking

In this new field it's important to keep track of how our tool is doing. To that
end we utilize the SDK provided by Tonic -
[Tonic Validate](https://docs.tonic.ai/validate/about-tonic-validate/tonic-validate-what-is).
More details on all of the
[metrics](https://docs.tonic.ai/validate/about-rag-metrics/tonic-validate-rag-metrics-summary).

What's cool here is we're sort of using the generative AI to test itself, as
there are metrics which call back to OpenAI asking the same question directly
(hence why it needs an evaluator model). In future these we will be extending
these metrics with things that interest us.

We will be hard at work creating new ones, but for now we use:

* Latency - Whether or not the answer takes longer than 5s. 0/1 (First place
  to add our custom metric 1 is good, 0 is bad, this is a bit limited)
  Measures LLM/Contextretriever.
* Answer Similarity - How well the reference answer matches the LLM answer.
  0-5 Measures all components
* Answer Consistency - Whether the LLM answer contains information that does
  not come from the context 0/1 (0 is no, 1 is yes) Measures the Prompt builder
  and LLM
* Augmentation accuracy - Whether all of the context is in the LLM answer. - Measures Prompt builder LLM
* Retrieval precision - Whether the context retrieved is relevant to answer
  the given question - Measures Chunker Embedder Retriever

Our particular implementation lives in the file "dragonfly_gauge.py" which can
be executed directly which can be called with the following options:

**Required args**
-q/--question_file QUESTION_FILE - Path to the json file containing:
                                   A "question" key with the question itself
                                   as the value.
                                   An "answer" key with the expected answer.
                                   Each of these should be in a new element.
                                   See the `example_benchmark_questions.json`
                                   file for referance.
-o/--org_name ORG_NAME  - The organization name from your lorelai database.
-u/--user_name USER_NAME - The username from your lorelai database

**Optional args**
--api_key  - This is the API key for the Tonic dashboard.
--project_id - The project ID from the Tonic dashboard. You can get it from
  the URL when you click on the desired project on their site: e.g
  [https://validate.tonic.ai/projects/88479076-9ca5-44bc-badd-75b68a6ae132](88479076-9ca5-44bc-badd-75b68a6ae132) is the ID
--evaluator - The evaluator model used for scoring metrics. We overwrite the
  default from the library to "gpt-3.5-turbo" since "gpt-4-turbo" is expensive

If the optional args are provided you will see your runs in the Tonic UI, else
you will get console output which can be piped into whatever is required.

Example run:

```bash
dragonfly_gauge.py --question_file questions.json --org_name "Big Business Inc" \
  --user_name ceo@bigbusiness.com --api_key VERY_SECRET_KEY --project_id SOME_ALPHA_NUMERIC
```
