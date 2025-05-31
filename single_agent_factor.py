import os
import json
import csv
import datetime
import time
import argparse
import re
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq

# Load environment variables from .env file
load_dotenv()

def get_openai_client():
    """
    Get OpenAI client with API key from environment
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables. Make sure .env file is loaded.")
    return OpenAI(api_key=openai_api_key)

def get_groq_client():
    """
    Get Groq client with API key from environment
    """
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables. Make sure .env file is loaded.")
    return Groq(api_key=groq_api_key)

# The argument developer agent task definition remains unchanged
Argument_Developer_Agent_Task = """
TASK
In this task, we will formulate legal arguments based on trade secret misappropriation claims using a structured approach. Follow the steps outlined below for consistency and clarity.

Legal Problem Context

In this problem, we aim to develop arguments using factors critical to trade secret misappropriation claims. Typically, the Plaintiff alleges that the Defendant has misappropriated their trade secret. For instance, Kentucky Fried Chicken (KFC) could claim misappropriation if an employee disclosed their secret recipe, which is a blend of herbs and spices, by publishing it in a cookbook.

Factors may support either the Plaintiff (P) or the Defendant (D). The Plaintiff might emphasize measures they took to protect the recipe, while the Defendant could argue that the recipe was already disclosed to outsiders. Based on the factors provided, construct a three-part argument as detailed below.

Instructions

    1.  If there is no common factor between the input case and the TSC1/TSC2, you need to say "No common factor between the input case and the TSC1/TSC2" and stop generating any argument.
    2.	Construct a 3-Ply Argument:
	i.	Plaintiff's Argument: Present an argument in favor of the Plaintiff's position by:
	•	Citing a relevant Trade Secret Case (TSC1/TSC2) with a similar favorable outcome.
	•	Highlighting shared factors between the input case and the TSC1/TSC2.
	ii.	Defendant's Counterargument: Refute the Plaintiff's position by:
	•	Distinguishing the cited TSC1/TSC2 based on differing factors.
	•	Citing a counterexample (a TSC1/TSC2 with a Defendant-favorable outcome) and drawing an analogy to the input case.
	iii.	Rebuttal by Plaintiff: Address and distinguish the counterexample, reinforcing the Plaintiff's original argument.
	3.	Use Provided Factors: Base your arguments on the factors outlined, ensuring logical consistency.

 
Example Input Case
    F1 Disclosure-in-negotiations (D)
	F4 Agreed-not-to-disclose (P)
	F6 Security-measures (P)
	F10 Secrets-disclosed-outsiders (D)
	F12 Outsider-disclosures-restricted (P)
	F14 Restricted-materials-used (P)
	F21 Knew-info-confidential (P)

Example TSC1
	outcome Plaintiff
	F4 Agreed-not-to-disclose (P)
	F6 Security-measures (P)
	F7 Brought-tools (P)
	F8 Competitive-advantage (P)
	F18 Identical-products (P)

Example TSC2
	outcome Defendant
	F3 Employee-sole-developer (D)
	F4 Agreed-not-to-disclose (P)
	F5 Agreement-not-specific (D)
	F6 Security-measures (P)
	F21 Knew-info-confidential (P)

Output Format:

```json
{
    {
      "Plaintiff's Argument": {
        "Factors F4 Agreed-not-to-disclose (P) and F6 Security-measures (P) were present in both the input case and TSC1, where the court found in favor of the Plaintiff. In Addition, Factors F12 Outsider-disclosures-restricted (P), F14 Restricted-materials-used (P), F21 Knew-info-confidential (P) are present in the input case and favor the Plaintiff."
      }
    },
    {
    "Defendant's Counterargument": {
        "TSC1, cited by the plaintiff is distinguishable because factors F7 Brought-tools (P), F8 Competitive-advantage (P), and F18 Identical-products (P) were also present, but are not present in the input case. In addition, F1 Disclosure-in-negotiations (D) and F10 Secrets-disclosed-outsiders (D) are pro-defendant strengths present in the input case but not in TSC1. TSC2 is a counterexample to TSC1. In TSC2, F4 Agreed-not-to-disclose (P), F6 Security-measures (P), and F21 Knew-info-confidential (P) were present in both the input case and TSC2 and the court found in favor of the Defendant."
      }
    },
    {
      "Plaintiff's Rebuttal": {
        "TSC2, cited by the Defendant is distinguishable. In TSC2, the additional factors F5 Agreement-not-specific (D) and F3 Employee-sole-developer (D) were present and are not present in input case. Also, F12 Outsider-disclosures-restricted (P) and F14 Restricted-materials-used (P) are present in the input case but not in TSC2."
      }
    }
}
```
"""

Factor_Distiller_Task = """
TASK
You are tasked with extracting factors from the argument.

Example Input:

{
    {
      "Plaintiff's Argument": {
        "Factors F4 Agreed-not-to-disclose (P) and F6 Security-measures (P) were present in both the input case and TSC1, where the court found in favor of the Plaintiff. In Addition, Factors F12 Outsider-disclosures-restricted (P), F14 Restricted-materials-used (P), F21 Knew-info-confidential (P) are present in the input case and favor the Plaintiff."
      }
    },
    {
      "Defendant's Counterargument": {
        "TSC1, cited by the plaintiff is distinguishable because factors F7 Brought-tools (P), F8 Competitive-advantage (P), and F18 Identical-products (P) were also present, but are not present in the input case. In addition, F1 Disclosure-in-negotiations (D) and F10 Secrets-disclosed-outsiders (D) are pro-defendant strengths present in the input case but not in TSC1. TSC2 is a counterexample to TSC1. In TSC2, F4 Agreed-not-to-disclose (P), F6 Security-measures (P), and F21 Knew-info-confidential (P) were present in both the input case and TSC2 and the court found in favor of the Defendant."
      }
    },
    {
      "Plaintiff's Rebuttal": {
        "TSC2, cited by the Defendant is distinguishable. In TSC2, the additional factors F5 Agreement-not-specific (D) and F3 Employee-sole-developer (D) were present and are not present in input case. Also, F12 Outsider-disclosures-restricted (P) and F14 Restricted-materials-used (P) are present in the input case but not in TSC2."
      }
    }
}

Example Output:
{
  "Input Case": {
    "F1 Disclosure-in-negotiations (D)",
	"F4 Agreed-not-to-disclose (P)",
	"F6 Security-measures (P)",
	"F10 Secrets-disclosed-outsiders (D)",
	"F12 Outsider-disclosures-restricted (P)",
	"F14 Restricted-materials-used (P)",
	"F21 Knew-info-confidential (P)"
  },
  "TSC1": {
    "F4 Agreed-not-to-disclose (P)",
    "F6 Security-measures (P)",
    "F7 Brought-tools (P)",
    "F8 Competitive-advantage (P)",
    "F18 Identical-products (P)"
  },
  "TSC2": {
    "F3 Employee-sole-developer (D)",
    "F4 Agreed-not-to-disclose (P)",
    "F5 Agreement-not-specific (D)",
    "F6 Security-measures (P)",
    "F21 Knew-info-confidential (P)"
  }
}
"""


def process_with_openai(client, model, prompt, system_prompt, temperature=0.1, max_tokens=2000):
    """Process a prompt using the OpenAI API"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def process_with_groq(client, model, prompt, system_prompt, temperature=0.1, max_tokens=2000):
    """Process a prompt using the Groq API"""
    # Special configurations for specific models
    kwargs = {}
    
    if model in ["qwen-qwq-32b", "deepseek-r1-distill-llama-70b"]:
        kwargs["response_format"] = {"type": "text"}
        # kwargs["reasoning_format"] = "raw"
        max_tokens = 6000  # Override max_tokens for these models
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )
    return response.choices[0].message.content

def setup_logging():
    """Set up logging for responses"""
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"{script_name}_responses_{timestamp}.json"
    
    log_data = []
    
    def log_response(scenario, argument, distilled_factors):
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "scenario": scenario,
            "argument": argument,
            "distilled_factors": distilled_factors
        }
        log_data.append(log_entry)
        
        # Write to file immediately to prevent data loss
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    
    return log_response

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate legal arguments using AI models")
    parser.add_argument("--model", 
                        choices=["gpt-4o-mini", "gpt-4o", "llama3-8b-8192", "llama3-70b-8192", 
                                "meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct", 
                                "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
                                "qwen-qwq-32b", "deepseek-r1-distill-llama-70b"], 
                        default="gpt-4o-mini", help="Model to use for argument generation")
    parser.add_argument("--input-file", help="Input file with custom scenarios to process")
    args = parser.parse_args()
    
    # Set up the appropriate clients
    openai_client = get_openai_client()
    groq_client = get_groq_client()
    
    # Print selected models
    print(f"Using {args.model} for argument generation")
    print(f"Using gpt-4.1 for factor distillation (fixed)")
    
    # Set up logging
    log_response = setup_logging()
    
    # Load input scenarios from CSV file
    csv_file_path = args.input_file if args.input_file else "data/Scenario_Factors.csv"
    print(f"Reading scenarios from: {csv_file_path}")
    
    # Read scenarios from CSV
    with open(csv_file_path, 'r') as file:
        csv_reader = csv.reader(file)
        
        # Try to skip header row if it exists
        try:
            header = next(csv_reader)
            # Check if this is actually a header or the first scenario
            if header and any(h.strip().lower().startswith("input scenario") for h in header):
                # This is a scenario, not a header - process it
                scenario_text = '\n'.join(header)
                
                # Process scenario with the appropriate client/model
                if args.model in ["gpt-4o-mini", "gpt-4o"]:
                    argument_response = process_with_openai(
                        openai_client, 
                        args.model, 
                        scenario_text, 
                        Argument_Developer_Agent_Task
                    )
                else:  # Groq models
                    argument_response = process_with_groq(
                        groq_client, 
                        args.model, 
                        scenario_text, 
                        Argument_Developer_Agent_Task
                    )
                
                # Extract the last JSON content if present
                pattern = r'```json(.*?)```'
                matches = re.findall(pattern, argument_response, re.DOTALL)
                
                if matches:
                    # Get the last match (last JSON snippet)
                    json_content = matches[-1].strip()
                    distiller_input = json_content
                else:
                    distiller_input = argument_response
                
                # Always use OpenAI for the distiller
                distiller_response = process_with_openai(
                    openai_client,
                    "gpt-4.1",
                    distiller_input,
                    Factor_Distiller_Task,
                    temperature=0.6,
                    max_tokens=1000
                )
                
                # Log the responses
                log_response(scenario_text, argument_response, distiller_response)
                
                # Print the responses
                print("\nArgument Response:")
                print(argument_response)
                print("\nDistilled Factors:")
                print(distiller_response)
                print("-" * 80)
                
                time.sleep(1)  # Rate limiting
                
        except StopIteration:
            # File is empty
            pass
                
        # Process the rest of the rows
        for row in csv_reader:
            if row:  # Skip empty rows
                scenario_text = '\n'.join(row)
                
                print(f"\nProcessing scenario:\n{scenario_text}\n")
                
                # Process scenario with the appropriate client/model
                if args.model in ["gpt-4o-mini", "gpt-4o"]:
                    argument_response = process_with_openai(
                        openai_client, 
                        args.model, 
                        scenario_text, 
                        Argument_Developer_Agent_Task
                    )
                else:  # Groq models
                    argument_response = process_with_groq(
                        groq_client, 
                        args.model, 
                        scenario_text, 
                        Argument_Developer_Agent_Task
                    )
                
                # Extract the last JSON content if present
                pattern = r'```json(.*?)```'
                matches = re.findall(pattern, argument_response, re.DOTALL)
                
                if matches:
                    # Get the last match (last JSON snippet)
                    json_content = matches[-1].strip()
                    distiller_input = json_content
                else:
                    distiller_input = argument_response
                
                # Always use OpenAI for the distiller
                distiller_response = process_with_openai(
                    openai_client,
                    "gpt-4.1",
                    distiller_input,
                    Factor_Distiller_Task,
                    temperature=0.6,
                    max_tokens=1000
                )
                
                # Log the responses
                log_response(scenario_text, argument_response, distiller_response)
                
                # Print the responses
                print("\nArgument Response:")
                print(argument_response)
                print("\nDistilled Factors:")
                print(distiller_response)
                print("-" * 80)
                
                time.sleep(1)  # Rate limiting

if __name__ == "__main__":
    main()