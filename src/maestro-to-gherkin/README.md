# Maestro Flow to Gherkin

This project automates the conversion of **Maestro** YAML flows into **Cucumber** Gherkin feature files. It uses **Jinja2** for templating and **PyYAML** for processing YAML files. The tool is designed to help testers and developers quickly transpile mobile automation flows into BDD-friendly formats.

## Features

- Transpiles Maestro YAML flow files into Cucumber Gherkin feature files.
- Supports multi-document YAML files (e.g., multiple flow steps).
- Automatically handles app initialization, input actions, and assertions.
- Customizable Gherkin templates using Jinja2 for flexibility.
- Removes unnecessary blank lines from the output Gherkin file.

## Prerequisites

Make sure you have the following installed:

- Python 3.7 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/maestro-flow-to-gherkin.git
    ```

2. Navigate to the project directory:

    ```bash
    cd maestro-flow-to-gherkin
    ```

3. Create a virtual environment (optional but recommended):

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```

4. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. **Prepare your Maestro YAML flow file**:
    Ensure that your Maestro YAML file is structured properly with two documents: 
    - The first document containing `appId`.
    - The second document containing the flow steps.

    Example Maestro YAML file:

    ```yaml
    appId: com.apple.mobilesafari
    ---
    - launchApp:
        clearState: true
    - tapOn: "Address"
    - inputText: "http://localhost:3000"
    - pressKey: Enter
    - tapOn: ".*Sign In.*"
    - assertVisible: "Login"
    - inputText:
        text: "kevin.lin@zuhlke.com"
        label: "Enter user email"
    - pressKey: Enter
    - assertVisible: ".*Sign in with your email address.*"
    - takeScreenshot: "ErbeCareIOS"
    ```

2. **Run the transpiler script**:

    Use the Python script `transpile.py` to convert the YAML file to a Gherkin feature file.

    ```bash
    python transpile.py
    ```

    This will generate a Gherkin feature file from the input YAML file, such as `output_feature.feature`.

3. **Customize Gherkin templates**:

    The Gherkin feature files are generated based on the template in `gherkin_template.j2`. You can modify this template to suit your needs.

## Example

Input Maestro YAML (`care_login_iOSflow.yaml`):

```yaml
appId: com.apple.mobilesafari
---
- launchApp:
    clearState: true
- tapOn: "Address"
- inputText: "http://localhost:3000"
- pressKey: Enter
- tapOn: ".*Sign In.*"
- assertVisible: "Login"