import argparse
from pathlib import Path
from dotenv import load_dotenv
from pretuning import generate, rebuild

if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parent / 'backend' / '.env', override=False)
    parser = argparse.ArgumentParser(description='Generate menu attribute dataframes with five web-search evaluations')
    parser.add_argument('--model', default='gpt-6luna', help='Exact OpenAI API model ID; must support Responses, web search and structured output')
    parser.add_argument('--from-run', help='Rebuild tables from five saved responses without API calls')
    parser.add_argument('--output', default='outputs/pretuning')
    args = parser.parse_args()
    if args.from_run:
        rebuild(args.from_run, args.output)
    else:
        generate(args.output, args.model)
