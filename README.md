\# Crypto AI Platform



An AI-powered cryptocurrency analysis platform designed to bring real-time market data, technical indicators, fundamental analysis, market news, machine learning predictions, and risk-aware decision support into one interface.



The platform combines a React and TypeScript frontend, a FastAPI backend, MongoDB storage, cryptocurrency market data providers, machine learning models, and Gemini-powered AI explanations.



> \*\*Disclaimer:\*\* This platform is intended for educational and informational purposes. Cryptocurrency markets are volatile, and predictions or analytical signals are not guarantees of future performance. Nothing in this project constitutes financial advice.



\## Table of Contents



\* \[Overview](#overview)

\* \[Features](#features)

\* \[Technology Stack](#technology-stack)

\* \[Architecture](#architecture)

\* \[Prerequisites](#prerequisites)

\* \[Project Structure](#project-structure)

\* \[Getting Started](#getting-started)

\* \[Environment Configuration](#environment-configuration)

\* \[Running the Application](#running-the-application)

\* \[Testing](#testing)

\* \[API Documentation](#api-documentation)

\* \[Machine Learning](#machine-learning)

\* \[Security](#security)

\* \[Troubleshooting](#troubleshooting)

\* \[Roadmap](#roadmap)

\* \[Contributing](#contributing)

\* \[License](#license)



\## Overview



Crypto AI Platform aims to simplify cryptocurrency research by combining market information and multiple analytical approaches in a single application.



Users can explore supported cryptocurrencies, review historical price movements, inspect technical and fundamental indicators, read cryptocurrency news, examine machine learning forecasts, and review risk-related metrics.



The application also provides AI-generated explanations to help users understand analytical results. AI explanations are intended to complement the underlying market data and decision engine rather than replace them.



\## Features



\### Cryptocurrency Markets



\* Cryptocurrency market overview and statistics.

\* Search for supported cryptocurrencies by name or symbol.

\* Coin-specific information and historical market data.

\* Market performance and price-change information.

\* Integration with supported cryptocurrency data providers.



\### Charts and Technical Analysis



\* Historical cryptocurrency price charts.

\* Technical indicator calculations.

\* Trend and momentum analysis.

\* Volatility-related measurements.

\* Technical summaries to support market research.



\### Fundamental Analysis



\* Available cryptocurrency project and market information.

\* Fundamental metrics where supported by the data provider.

\* Structured summaries to assist cryptocurrency research.



\### News and Sentiment



\* Cryptocurrency news integration.

\* News-related sentiment analysis where supported.

\* Contextual information for researching market movements.



\### Machine Learning Predictions



\* Machine learning prediction pipeline.

\* Support for configured prediction models.

\* Historical data processing and feature engineering.

\* Model evaluation and prediction-related metrics.

\* Sequence and tree-based model support where configured.



Predictions depend on the available historical data, model configuration, and model performance. They should not be interpreted as guaranteed price targets.



\### AI-Powered Analysis



\* Gemini-powered explanations where configured.

\* Structured analytical summaries.

\* AI-generated interpretations of available market information.

\* Separation between AI-generated explanations and deterministic decision-engine calculations.



\### Risk and Decision Support



\* Risk-related measurements.

\* Decision support based on available market inputs.

\* Insufficient-data handling when the required information is unavailable.

\* Analytical outputs intended to support, not automate, investment decisions.



\### User Features



The application includes user authentication and supporting features such as watchlists, portfolio tracking, alerts, historical records, and account settings, subject to the enabled backend configuration.



\## Technology Stack



| Component           | Technology                                            |

| ------------------- | ----------------------------------------------------- |

| Frontend            | React, TypeScript, Vite                               |

| Styling             | Tailwind CSS                                          |

| Backend             | Python, FastAPI                                       |

| Database            | MongoDB                                               |

| API documentation   | OpenAPI, Swagger UI                                   |

| Cryptocurrency data | Configured providers, including CoinGecko and Binance |

| AI analysis         | Google Gemini API                                     |

| Machine learning    | Python ML libraries and configured models             |

| Testing             | Pytest, frontend test tooling                         |

| Version control     | Git and GitHub                                        |



The availability of individual features depends on the environment variables, external API access, database configuration, and model artifacts configured for the project.



\## Architecture



The platform is organized into three main layers:



1\. \*\*Frontend:\*\* Presents dashboards, cryptocurrency information, charts, news, and user features.

2\. \*\*Backend API:\*\* Handles authentication, application logic, market-data integration, analysis, prediction workflows, and API responses.

3\. \*\*Data and analysis layer:\*\* Uses MongoDB, external market-data providers, configured machine learning models, and the Gemini API where enabled.



The decision engine is designed to provide analytical results independently of AI-generated explanations.



\## Prerequisites



Install the following before running the project:



\* Python compatible with the backend's dependency configuration.

\* Node.js and npm.

\* MongoDB, either locally or through a hosted deployment.

\* Git.

\* API credentials for any external providers you intend to use.



You should also have access to the project's configured Gemini API model if you want Gemini-powered features.



\## Project Structure



The repository follows this general layout. Some filenames may differ depending on the current implementation.



```text

crypto-ai-platform/

├── backend/

│   ├── app/

│   │   ├── main.py

│   │   ├── services/

│   │   └── repositories/

│   ├── tests/

│   ├── .venv/

│   ├── requirements.txt

│   └── .env

├── frontend/

│   ├── src/

│   ├── public/

│   ├── package.json

│   └── vite.config.ts

├── ml/

│   ├── datasets/

│   ├── models/

│   ├── experiments/

│   └── artifacts/

├── .gitignore

└── README.md

```



\*\*Note:\*\* This is a representative structure. Use the actual folders and filenames in your repository as the source of truth.



\## Getting Started



\### 1. Clone the repository



```bash

git clone https://github.com/souvik-mondal-07/crypto-ai-platform.git

cd crypto-ai-platform

```



If you already have the repository locally, open its root directory instead.



\### 2. Set up the backend



Open PowerShell in the repository root:



```powershell

cd backend

```



Create a virtual environment if one does not already exist:



```powershell

python -m venv .venv

```



Activate it:



```powershell

.\\.venv\\Scripts\\Activate.ps1

```



Install dependencies:



```powershell

python -m pip install --upgrade pip

pip install -r requirements.txt

```



If PowerShell blocks virtual-environment activation, you can use the environment's Python executable directly:



```powershell

.\\.venv\\Scripts\\python.exe -m pytest -q

```



\### 3. Set up the frontend



Open a second PowerShell terminal:



```powershell

cd "D:\\Crypto Project\\crypto-ai-platform\\crypto-ai-platform\\frontend"

```



Install dependencies:



```powershell

npm install

```



\## Environment Configuration



Create or update the backend environment file at:



`backend\\.env`



Use the variable names required by your actual settings implementation. A conceptual example is shown below; these names are illustrative and must be matched to the project's configuration.



```dotenv

MONGODB\_URI=mongodb://localhost:27017

DATABASE\_NAME=crypto\_ai\_platform



GEMINI\_API\_KEY=your\_gemini\_api\_key



COINGECKO\_API\_KEY=

BINANCE\_BASE\_URL=https://api.binance.com

```



Before starting the application:



1\. Confirm that the MongoDB connection string matches your database setup.

2\. Configure the Gemini credential if AI-powered features require it.

3\. Configure market-data provider credentials if required by your implementation.

4\. Confirm that the configured Gemini model identifier is supported.

5\. Keep secrets in environment variables rather than source code.



\*\*Important:\*\* The variable names above are examples, not a verified inventory of your application's settings. Check the backend configuration and existing environment template before using them. Do not commit `.env` files or publish API keys.



\## Running the Application



Run the backend and frontend in separate terminals.



\### Terminal 1: Start FastAPI



From the repository root:



```powershell

cd "D:\\Crypto Project\\crypto-ai-platform\\crypto-ai-platform\\backend"

.\\.venv\\Scripts\\Activate.ps1

uvicorn app.main:app --reload

```



The development server should be available at:



\* API base: http://127.0.0.1:8000

\* Swagger UI: http://127.0.0.1:8000/docs

\* OpenAPI schema: http://127.0.0.1:8000/openapi.json



The exact endpoints depend on the routes registered by the backend.



\### Terminal 2: Start Vite



```powershell

cd "D:\\Crypto Project\\crypto-ai-platform\\crypto-ai-platform\\frontend"

npm run dev

```



Open the local URL printed by Vite, commonly:



http://localhost:5173



Keep both terminals open while using the application.



\## Testing



\### Backend tests



From the backend directory, activate the virtual environment and run:



```powershell

python -m pytest -q

```



For verbose output:



```powershell

python -m pytest -v

```



To run a specific test file:



```powershell

python -m pytest tests/test\_no\_fake\_data.py -q

```



\### Frontend tests



From the frontend directory:



```powershell

npm run test

```



If the test script does not support the default invocation, check the scripts defined in `frontend/package.json`. For a Vite project using Vitest, the following is commonly available:



```powershell

npm run test -- --run

```



\### Frontend production build



```powershell

npm run build

```



Run the tests and build before submitting significant changes. A successful test suite does not guarantee that every external API, database service, or integration works in the running application.



\## API Documentation



When the backend is running, open:



http://127.0.0.1:8000/docs



Swagger UI allows you to inspect registered endpoints, view request and response schemas, and test API operations.



The OpenAPI schema is available at:



http://127.0.0.1:8000/openapi.json



Use the actual API documentation to identify supported routes rather than assuming every planned endpoint is implemented.



\## Machine Learning



The ML layer supports the project's configured data-processing, training, evaluation, and prediction workflows.



Typical responsibilities include:



\* Preparing historical market data.

\* Engineering model features.

\* Training configured models.

\* Evaluating prediction quality.

\* Generating predictions using available model artifacts.

\* Handling missing or insufficient input data.



Generated model artifacts and datasets may be excluded from version control. Follow the repository's `.gitignore` rules and document any required setup steps for reproducing model outputs.



Do not treat historical accuracy as a guarantee of future results.



\## Security



\* Never commit API keys, passwords, access tokens, or database credentials.

\* Keep local environment files out of version control.

\* Validate and sanitize user inputs.

\* Protect authenticated routes with the configured authentication mechanisms.

\* Use HTTPS and secure deployment configuration in production.

\* Apply appropriate rate limits to public-facing APIs.

\* Avoid exposing internal errors or sensitive configuration in API responses.

\* Do not allow AI-generated content to bypass authorization or business rules.



\## Troubleshooting



\### Backend does not start



Confirm that you are in the backend directory and the virtual environment exists:



```powershell

Test-Path ".\\.venv\\Scripts\\python.exe"

```



Then inspect the terminal error and verify installed dependencies.



\### Frontend does not start



Check your Node.js and npm installations:



```powershell

node --version

npm --version

```



Install dependencies if necessary:



```powershell

npm install

npm run dev

```



\### MongoDB connection fails



\* Confirm MongoDB is running or the hosted database is reachable.

\* Verify the connection string and database permissions.

\* Check network access and any required IP allowlist settings.

\* Review backend logs without exposing credentials.



\### Market data is unavailable



\* Verify external provider availability and API limits.

\* Check the configured API keys and provider settings.

\* Review backend logs for request failures.

\* Distinguish unavailable data from valid zero values or stale cached data.



\### Gemini analysis is unavailable



\* Confirm that the Gemini API key is configured.

\* Check model configuration, API access, quotas, and request errors.

\* Verify that the requested analysis has the required input data.



\### Tests fail



Run the failing test individually to isolate the issue:



```powershell

python -m pytest tests/test\_no\_fake\_data.py -v

```



Review the assertion and implementation before changing tests or suppressing errors.



\## Roadmap



Potential areas for further development include:



\* Improving market-data coverage and reliability.

\* Expanding analytical dashboards and technical indicators.

\* Improving model evaluation and prediction monitoring.

\* Enhancing AI-generated explanations and transparency.

\* Improving risk metrics and insufficient-data handling.

\* Expanding automated testing and integration coverage.

\* Improving accessibility, responsive design, and production deployment readiness.



This roadmap describes possible improvements and does not imply that every item is currently implemented.



\## Contributing



Contributions and suggestions are welcome.



1\. Create a feature branch.

2\. Make a focused change.

3\. Add or update tests.

4\. Run relevant backend tests and frontend checks.

5\. Commit using a descriptive message.

6\. Submit a pull request with a summary of the change.



Example commit message:



```text

fix: improve market data validation

```



\## License



No license is specified in this README. Before distributing or reusing the project, add a `LICENSE` file and select a license that reflects the project's intended usage.



