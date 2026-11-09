import argparse
from pathlib import Path
from dotenv import load_dotenv
from pretuning import generate, rebuild, prepare

if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parent / 'backend' / '.env', override=False)
    parser = argparse.ArgumentParser(description='Generate menu attribute dataframes with five web-search evaluations')
    parser.add_argument('--model', default='gpt-4.1', help='Exact OpenAI API model ID; must support Responses, web search and structured output')
    parser.add_argument('--from-run', help='Rebuild tables from five saved responses without API calls')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-only', action='store_true', help='Export catalogue and binary scores without API calls')
    modes.add_argument('--resume', action='store_true', help='Continue the same catalogue/model evaluation directory')
    parser.add_argument('--output', default='outputs/pretuning')
    args = parser.parse_args()
    if args.from_run and (args.prepare_only or args.resume):
        parser.error('--from-run cannot be combined with --prepare-only or --resume')
    if args.prepare_only:
        print(f'Prepared {prepare(args.output)}; taste evaluation still pending')
    elif args.from_run:
        rebuild(args.from_run, args.output)
    else:
        generate(args.output, args.model, resume=args.resume)
