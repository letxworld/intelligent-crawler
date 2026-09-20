# Intelligent Crawler

A lightweight crawler that executes JavaScript, extracts API endpoints from loaded scripts, and guesses hidden parameters from discovered routes.

## Features

- Execute and crawl JavaScript-heavy pages
- Extract API endpoints from inline and remote scripts
- Discover hidden parameters by analyzing endpoint patterns
- Output results in JSON for easy downstream processing

## Requirements

- Node.js 18+
- npm 9+

## Installation

```bash
git clone https://github.com/letxworld/intelligent-crawler.git
cd intelligent-crawler
npm install
```

## Usage

```bash
npm start -- https://example.com
```

## Output

Endpoints and guessed parameters are written to `output.json`.

## Development

```bash
npm test
```

## License

MIT
