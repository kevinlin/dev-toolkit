import yaml
from jinja2 import Environment, FileSystemLoader


# Load Maestro YAML file with multiple documents
def load_yaml(file_path):
    with open(file_path) as file:
        return list(yaml.safe_load_all(file))  # Load all YAML documents


# Set up Jinja2 environment
def setup_jinja_env(template_dir):
    return Environment(loader=FileSystemLoader(template_dir))


# Render the Gherkin feature file
def render_gherkin(template, data, output_file):
    output = template.render(data)
    with open(output_file, 'w') as file:
        file.write(output)


# Main function to transpile Maestro YAML to Gherkin
def transpile(maestro_yaml_file, template_file, output_file):
    # Load YAML with multiple documents
    maestro_docs = load_yaml(maestro_yaml_file)

    # Check that the first document is a dictionary
    if not isinstance(maestro_docs[0], dict):
        raise ValueError(f"Expected dictionary but got {type(maestro_docs[0])}")

    # Check that the second document is a list (the steps/flow)
    if not isinstance(maestro_docs[1], list):
        raise ValueError(f"Expected list but got {type(maestro_docs[1])}")

    # Combine the two documents: app data (1st) and flow data (2nd)
    maestro_data = maestro_docs[0]  # The appId part
    maestro_data['flow'] = maestro_docs[1]  # The list of steps

    # Set up Jinja2 environment
    env = setup_jinja_env('.')

    # Load Jinja2 template
    template = env.get_template(template_file)

    # Render Gherkin file from Maestro YAML data
    # render_gherkin(template, app_data, output_file)
    render_gherkin(template, maestro_data, output_file)


# Example usage
if __name__ == "__main__":
    maestro_yaml = "input/empower_flowiOS.yaml"
    gherkin_template = "gherkin_template.j2"
    output_feature = "output/empower_flowiOS.yaml.feature"

    transpile(maestro_yaml, gherkin_template, output_feature)
    print(f"Gherkin feature file generated: {output_feature}")
