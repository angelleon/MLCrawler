# MLCrawler

## Features in this project
- Test suite (not complted) in `src/test`
- Dockerfile for building a container image
- Github action defined for lint, test and contianer build
## Run this project
0. Host configuration
    This project was proven using following software configuration
    - Python 3.10
    - Pip 22.0
    - virtualenv 20.13
    - Manajro Linux 21.2
    - Surfshark VPN, Mexico location
1. Install dependencies
    ```shell
    virtualenv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2. Run
    By default the program will read categories.txt, this behaivor can be customized using the `--categories option` (short option `-c`)
    ```shell
    source venv/bin/activate
    cd src/crawler
    python crawler.py -c CATEGORIES_FILE
    ```
3. Run tests
    ```shell
    source venv/bin/activate
    cd src/
    python -m pytest -s .
    ```
4. Build container image. \
The user is memeber of group docker. For non-members of that group execute this with `sudo`
    ```shell
    docker -t IMAGE_NAME:TAG .
    ```
5. Known issues
    - Pending features for implement
        - product info extraction
        - stop mechanism
    - Tests broken after latest changes
    - Low test coverage


