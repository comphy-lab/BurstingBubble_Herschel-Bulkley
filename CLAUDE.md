## Documentation Generation

- Read `.github/README.md` for the website generation process.
- Do not auto-deploy the website; generating HTML is permitted using `.github/scripts/build.sh`.
- Avoid editing HTML files directly; they are generated using `.github/scripts/build.sh`, which utilizes `.github/scripts/generate_docs.py`.
- The website is deployed at `https://comphy-lab.org/repositoryName`; refer to the `CNAME` file for configuration. Update if not done already. 


# For the Basilisk CFD code parts:

## Purpose

This rule provides guidance for maintaining and generating documentation for code repositories in the CoMPhy Lab, ensuring consistency and proper workflow for website generation.

## Process Details

The documentation generation process utilizes Python scripts to convert source code files into HTML documentation. The process handles C/C++, Python, Shell, and Markdown files, generating a complete documentation website with navigation, search functionality, and code highlighting.

## Best Practices

- Always use the build script for generating documentation rather than manually editing HTML files
- Customize styling through CSS files in `.github/assets/css/`
- Modify functionality through JavaScript files in `.github/assets/js/`
- For template changes, edit `.github/assets/custom_template.html`
- Troubleshoot generation failures by checking error messages and verifying paths and dependencies


## Purpose

This document outlines the coding standards, project structure, and best practices for computational fluid dynamics simulations using the Basilisk framework. Following these standards ensures code readability, maintainability, and reproducibility across the CoMPhy Lab's research projects.

## Project Structure

- `basilisk/src/`: Core Basilisk CFD library (read-only).
- `src-local/`: Custom headers extending Basilisk functionality.
- `postProcess/`: Project-specific post-processing tools.
- `simulationCases/`: Test cases with individual Makefiles.

## Code Style

- **Indentation**: 2 spaces (no tabs).
- **Line Length**: Maximum 80 characters per line.
- **Comments**: Use markdown in comments starting with `/**`; avoid bare `*` in comments.
- **Spacing**: Include spaces after commas and around operators (`+`, `-`).
- **File Organization**: 
  - Place core functionality in `.h` headers
  - Implement tests in `.c` files
- **Naming Conventions**: 
  - Use `snake_case` for variables and parameters
  - Use `camelCase` for functions and methods
- **Error Handling**: Return meaningful values and provide descriptive `stderr` messages.

## Build & Test Commands

**Standard Compilation**:

```bash
qcc -autolink file.c -o executable -lm
```

## Compilation with Custom Headers:

```bash
qcc -I$PWD/src-local -autolink file.c -o executable -lm
```


## Best Practices
- Keep simulations modular and reusable
- Document physical assumptions and numerical methods
- Perform mesh refinement studies to ensure solution convergence
- Include visualization scripts in the postProcess directory