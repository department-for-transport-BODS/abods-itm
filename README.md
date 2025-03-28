# ABODS Integrated Data Management (ITM)

## 📋 Overview

This repository powers the **Analyse Bus Open Data Service** offered by the UK Department for Transport.
It handles backend processing of **timetable** and **real-time AVL** data from BODS, and performs On-Time Performance (OTP) matching and analysis.

## 🚀 Tech Stack

- **Database:** Liquibase
- **Development:** Python 3.13+
- **Infrastructure:** AWS SAM
- **CI/CD:** GitHub Actions

## 🏗️ Architecture

- **Timetable Data:** Copied from BODS database to ABODS database
- **AVL Data:** Ingested from IAVL every 10s, stored in S3, and written to ABODS database
- **OTP Matching:** Processes data to generate matching results
- **Summaries:** Created for the [ABODS front end](https://github.com/department-for-transport-BODS/abods)

See [Architecture Guide](./docs/Architecture.md) for details.

## 🛠️ Getting Started

To set up your local development environment and start contributing, follow the [Getting Started Guide](./docs/Getting%20Started.md).

### 📦 Deployment

For instructions on deploying through the path to live, refer to the [Deployment Guide](./docs/Deployment.md).

## ⚙️ Operations

Day-to-day operational tips and best practices can be found in the [Operations Guide](./docs/Operations.md).
