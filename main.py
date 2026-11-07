import argparse
from pathlib import Path
from dotenv import load_dotenv
from pretuning import generate

if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parent / 'backend' / '.env', override=False)
    parser = argparse.ArgumentParser(description='Generate menu attribute dataframes with five web-search evaluations')
    parser.add_argument('--model', default='gpt-6luna', help='Exact OpenAI API model ID; must support Responses, web search and structured output')
    parser.add_argument('--prices', default='common/menu_prices.json')
    parser.add_argument('--output', default='outputs/pretuning')
    args = parser.parse_args()
    generate(args.prices, args.output, args.model)
