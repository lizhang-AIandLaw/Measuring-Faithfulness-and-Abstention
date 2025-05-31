import random
import re
import json
import csv
import string
import argparse
import sys

class ScenarioGenerator():
    # Map new mode names to internal mode names
    MODE_MAPPING = {
        "non-arguable": "unarguable",
        "reordered": "reordered",
        "arguable": "arguable"
    }
    
    def __init__(self, mode1="reordered", mode2="reordered", complexity=5):
        # Output format is now fixed to "factor"
        output_format = "factor"
        print(f"Initializing generator with mode1={mode1}, mode2={mode2}, format={output_format}, complexity={complexity}")
        self.factors = [
            "F1 Disclosure-in-negotiations (D)", 
            "F2 Bribe-employee (P)", 
            "F3 Employee-sole-developer (D)", 
            "F4 Agreed-not-to-disclose (P)", 
            "F5 Agreement-not-specific (D)", 
            "F6 Security-measures (P)", 
            "F7 Brought-tools (P)", 
            "F8 Competitive-advantage (P)", 
            "F10 Secrets-disclosed-outsiders (D)", 
            "F11 Vertical-knowledge (D)", 
            "F12 Outsider-disclosures-restricted (P)", 
            "F13 Noncompetition-agreement (P)", 
            "F14 Restricted-materials-used (P)", 
            "F15 Unique-product (P)", 
            "F16 Info-reverse-engineerable (D)", 
            "F17 Info-independently-generated (D)", 
            "F18 Identical-products (P)", 
            "F19 No-security-measures (D)", 
            "F20 Info-known-to-competitors (D)", 
            "F21 Knew-info-confidential (P)", 
            "F22 Invasive-techniques (P)", 
            "F23 Waiver-of-confidentiality (D)", 
            "F24 Info-obtainable-elsewhere (D)", 
            "F25 Info-reverse-engineered (D)", 
            "F26 Deception (P)", 
            "F27 Disclosure-in-public-forum (D)"
        ]
        
        if mode1 in self.MODE_MAPPING:
            self.mode1 = self.MODE_MAPPING[mode1]
        elif mode1 in self.MODE_MAPPING.values():
            self.mode1 = mode1
        else:
            self.mode1 = "reordered"  # Default
            
        if mode2 in self.MODE_MAPPING:
            self.mode2 = self.MODE_MAPPING[mode2]
        elif mode2 in self.MODE_MAPPING.values():
            self.mode2 = mode2
        else:
            self.mode2 = "reordered"  # Default
            
        print(f"Internal modes: mode1={self.mode1}, mode2={self.mode2}")
        self.output_format = output_format # Always factor
        self.complexity = complexity
        print("Generating initial scenario...")
        self.input_factors, self.tsc1, self.tsc2 = self.generate_input_scenario()
        print("Initialization complete.")

    def generate_input_factor(self):
        print("Generating input factors...")
        selected_factors = []
        used_indices = set()
        
        min_factors = max(1, self.complexity - 1)
        max_factors = self.complexity + 1
        target_count = random.randint(min_factors, max_factors)
        print(f"Target count for input factors: {target_count}")
        
        while len(selected_factors) < target_count:
            index = random.randint(0, len(self.factors) - 1)
            if index not in used_indices:
                selected_factors.append(self.factors[index])
                used_indices.add(index)
        
        print(f"Generated {len(selected_factors)} input factors")
        return selected_factors

    def generate_tsc_factor(self, input_factors, mode="unarguable", is_tsc1=True):
        tsc_type = "TSC1" if is_tsc1 else "TSC2"
        print(f"Generating {tsc_type} factors with mode: {mode}...")
        selected_factors = []
        used_indices = set()
        
        min_factors = max(1, self.complexity - 1)
        max_factors = self.complexity + 1
        target_count = random.randint(min_factors, max_factors)
        print(f"Target count for {tsc_type}: {target_count}")
        
        if mode == "arguable":
            # Get pro-defendant and pro-plaintiff factors from input
            input_d_factors = [f for f in input_factors if "(D)" in f]
            input_p_factors = [f for f in input_factors if "(P)" in f]
            
            if is_tsc1:
                # For TSC1: 1-3 pro-plaintiff factors
                if input_p_factors:  # Check if there are any P factors
                    n_common = random.randint(1, min(3, len(input_p_factors)))
                    common_factors = random.sample(input_p_factors, n_common)
                    selected_factors.extend(common_factors)
                    used_indices.update(self.factors.index(f) for f in common_factors)
            else:
                # For TSC2: 1-3 pro-defendant factors 
                if input_d_factors:  # Check if there are any D factors
                    n_common = random.randint(1, min(3, len(input_d_factors)))
                    common_factors = random.sample(input_d_factors, n_common)
                    selected_factors.extend(common_factors)
                    used_indices.update(self.factors.index(f) for f in common_factors)
            
            # Maybe add some other shared factors
            other_factors = [f for f in input_factors if f not in selected_factors]
            if other_factors and random.random() < 0.7: # Increased probability
                n_other = random.randint(1, min(3, len(other_factors))) # Increased max number
                selected_factors.extend(random.sample(other_factors, n_other))
            
            # Add random factors to reach desired length
            while len(selected_factors) < target_count:
                factor = random.choice(self.factors)
                if factor not in selected_factors:
                    selected_factors.append(factor)
        else:
            # Default unarguable mode: ensure absolutely no common factors
            print(f"Using unarguable mode for {tsc_type}")
            available_factors = [f for f in self.factors if f not in input_factors]
            print(f"Available unique factors: {len(available_factors)}")
            
            # Verify we have enough unique factors
            if len(available_factors) < target_count:
                # Adjust the target count if we don't have enough unique factors
                print(f"Not enough unique factors. Adjusting target count from {target_count} to {len(available_factors)}")
                target_count = len(available_factors)
            
            # Select random factors from available factors (none from input)
            try:
                selected_factors = random.sample(available_factors, target_count)
                print(f"Selected {len(selected_factors)} factors for {tsc_type}")
            except ValueError as e:
                print(f"Error selecting factors: {e}")
                print(f"Available factors: {len(available_factors)}, Target count: {target_count}")
                # Fallback selection
                selected_factors = available_factors[:target_count]
                    
        return selected_factors

    def find_common_factors(self, tsc):
        if tsc == "tsc1":
            tsc_factor = self.tsc1
        elif tsc == "tsc2":
            tsc_factor = self.tsc2
        common_factors = [factor for factor in self.input_factors if factor in tsc_factor]

        return common_factors

    def generate_input_scenario(self):
        print("Generating complete scenario...")
        input_factors = self.generate_input_factor()
        print(f"Input factors: {len(input_factors)}")
        
        # For reordered mode, we'll generate both TSCs using arguable mode first, then swap
        if self.mode1 == "reordered" and self.mode2 == "reordered":
            print("Using reordered mode: generating with arguable mode then swapping outcomes")
            print("Generating TSC1 with arguable mode")
            tsc1 = self.generate_tsc_factor(input_factors, mode="arguable", is_tsc1=True)
            
            print("Generating TSC2 with arguable mode")
            tsc2 = self.generate_tsc_factor(input_factors, mode="arguable", is_tsc1=False)
            
            # Swap TSC1 and TSC2 to implement reordered mode
            print("Swapping TSC1 and TSC2 for reordered mode")
            tsc1, tsc2 = tsc2, tsc1
        else:
            # Standard generation for other modes
            print(f"Generating TSC1 with mode: {self.mode1}")
            tsc1 = self.generate_tsc_factor(input_factors, mode=self.mode1, is_tsc1=True)
            
            print(f"Generating TSC2 with mode: {self.mode2}")
            tsc2 = self.generate_tsc_factor(input_factors, mode=self.mode2, is_tsc1=False)
        
        # For unarguable mode, double-check that there are no overlaps
        if self.mode1 == "unarguable":
            common_factors = [f for f in input_factors if f in tsc1]
            if common_factors:
                print(f"Found overlapping factors in TSC1: {len(common_factors)}. Regenerating.")
                tsc1 = self.generate_tsc_factor(input_factors, mode=self.mode1, is_tsc1=True)
            else:
                print("No overlaps found in TSC1.")
                
        if self.mode2 == "unarguable":
            common_factors = [f for f in input_factors if f in tsc2]
            if common_factors:
                print(f"Found overlapping factors in TSC2: {len(common_factors)}. Regenerating.")
                tsc2 = self.generate_tsc_factor(input_factors, mode=self.mode2, is_tsc1=False)
            else:
                print("No overlaps found in TSC2.")
        
        return input_factors, tsc1, tsc2

    def extract_factor_number(self, factor):
        match = re.match(r"F(\d+)", factor)
        return int(match.group(1)) if match else float('inf')

    def generate_initial_prompt(self):
        print("Generating prompt...")
        # Output format is always "factor"
        input_scenario_items = sorted(self.input_factors, key=lambda x: int(re.search(r'\\d+', x).group()))
        tsc1_factors_items = sorted(self.tsc1, key=lambda x: int(re.search(r'\\d+', x).group()))
        tsc2_factors_items = sorted(self.tsc2, key=lambda x: int(re.search(r'\\d+', x).group()))
        
        input_scenario_str = ",\\n\t".join(input_scenario_items)
        tsc1_factors_str = ",\\n\t".join(tsc1_factors_items)
        tsc2_factors_str = ",\\n\t".join(tsc2_factors_items)

        # For reordered mode, we swap the outcomes
        if self.mode1 == "reordered" and self.mode2 == "reordered":
            input_scenario_prompt = f"""
Input Scenario 
\t{input_scenario_str}

TSC 1
outcome Defendant
\t{tsc1_factors_str}

TSC 2
outcome Plaintiff
\t{tsc2_factors_str}
"""
        else:
            input_scenario_prompt = f"""
Input Scenario 
\t{input_scenario_str}

TSC 1
outcome Plaintiff
\t{tsc1_factors_str}

TSC 2
outcome Defendant
\t{tsc2_factors_str}
"""
        return input_scenario_prompt

    def update_tsc(self, tsc_name, mode="citable"):
        # Handle mode mapping if needed
        if mode in self.MODE_MAPPING:
            internal_mode = self.MODE_MAPPING[mode]
        elif mode in self.MODE_MAPPING.values():
            internal_mode = mode
        else:
            internal_mode = "reordered"  # Default
            
        print(f"Updating {tsc_name} with mode {internal_mode}")
        
        if internal_mode == "reordered":
            # For reordered mode, generate both TSCs with arguable mode then swap
            print("Using reordered mode: generating with arguable mode then swapping outcomes")
            self.tsc1 = self.generate_tsc_factor(self.input_factors, mode="arguable", is_tsc1=True)
            self.tsc2 = self.generate_tsc_factor(self.input_factors, mode="arguable", is_tsc1=False)
            # Swap TSC1 and TSC2 to implement reordered mode
            print("Swapping TSC1 and TSC2 for reordered mode")
            self.tsc1, self.tsc2 = self.tsc2, self.tsc1
        else:
            # Standard generation for other modes
            if tsc_name == "tsc1":
                self.tsc1 = self.generate_tsc_factor(self.input_factors, mode=internal_mode, is_tsc1=True)
                # For unarguable mode, ensure no overlaps
                if internal_mode == "unarguable":
                    attempts = 0
                    while any(factor in self.input_factors for factor in self.tsc1) and attempts < 5:
                        print(f"Found overlapping factors in TSC1 update. Regenerating (attempt {attempts+1}).")
                        self.tsc1 = self.generate_tsc_factor(self.input_factors, mode=internal_mode, is_tsc1=True)
                        attempts += 1
                    if attempts >= 5:
                        print("Warning: Could not eliminate overlaps after 5 attempts.")
            elif tsc_name == "tsc2":
                self.tsc2 = self.generate_tsc_factor(self.input_factors, mode=internal_mode, is_tsc1=False)
                # For unarguable mode, ensure no overlaps
                if internal_mode == "unarguable":
                    attempts = 0
                    while any(factor in self.input_factors for factor in self.tsc2) and attempts < 5:
                        print(f"Found overlapping factors in TSC2 update. Regenerating (attempt {attempts+1}).")
                        self.tsc2 = self.generate_tsc_factor(self.input_factors, mode=internal_mode, is_tsc1=False)
                        attempts += 1
                    if attempts >= 5:
                        print("Warning: Could not eliminate overlaps after 5 attempts.")
            else:
                raise ValueError("Invalid TSC name. Use 'tsc1' or 'tsc2'.")

        # Output format is always "factor"
        input_scenario_items = sorted(self.input_factors, key=self.extract_factor_number)
        tsc1_factors_items = sorted(self.tsc1, key=self.extract_factor_number)
        tsc2_factors_items = sorted(self.tsc2, key=self.extract_factor_number)
        
        input_scenario_str = ",\\n\t".join(input_scenario_items)
        tsc1_factors_str = ",\\n\t".join(tsc1_factors_items)
        tsc2_factors_str = ",\\n\t".join(tsc2_factors_items)

        # For reordered mode, we swap the outcomes
        if internal_mode == "reordered":
            input_scenario_prompt = f"""
Input Scenario 
\t{input_scenario_str}

TSC 1
outcome Defendant
\t{tsc1_factors_str}

TSC 2
outcome Plaintiff
\t{tsc2_factors_str}
"""
        else:
            input_scenario_prompt = f"""
Input Scenario 
\t{input_scenario_str}

TSC 1
outcome Plaintiff
\t{tsc1_factors_str}

TSC 2
outcome Defendant
\t{tsc2_factors_str}
"""
        return input_scenario_prompt

    def restart(self):
        print("Restarting scenario generation...")
        self.input_factors, self.tsc1, self.tsc2 = self.generate_input_scenario()
        print("Restart complete.")

def generate_datasets(mode="non-arguable", case_number=10, complexity=5):
    # Output format is now fixed to "factor"
    output_format="factor"
    print(f"Generating {case_number} scenarios with mode={mode}, format={output_format}, complexity={complexity}")
    
    # Do mode mapping directly
    if mode in ScenarioGenerator.MODE_MAPPING:
        internal_mode = ScenarioGenerator.MODE_MAPPING[mode]
    elif mode in ScenarioGenerator.MODE_MAPPING.values():
        internal_mode = mode
    else:
        internal_mode = "unarguable"  # Default to unarguable if invalid
        
    print(f"Internal mode: {internal_mode}")
    
    # Generate the specified number of sets
    scenario_sets = []
    for i in range(case_number):
        print(f"Generating scenario {i+1}/{case_number}")
        gen = ScenarioGenerator(mode1=internal_mode, mode2=internal_mode, complexity=complexity)
        
        # Verify that in unarguable mode there are no overlapping factors
        if internal_mode == "unarguable":
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                common_tsc1 = [f for f in gen.input_factors if f in gen.tsc1]
                common_tsc2 = [f for f in gen.input_factors if f in gen.tsc2]
                
                if common_tsc1 or common_tsc2:
                    print(f"Found overlaps after generation. TSC1: {len(common_tsc1)}, TSC2: {len(common_tsc2)}. Restarting ({attempt+1}/{max_attempts}).")
                    gen.restart()
                    attempt += 1
                else:
                    print("No overlaps found. Scenario is valid.")
                    break
                    
            if attempt >= max_attempts:
                print(f"Warning: Could not eliminate all overlaps after {max_attempts} attempts.")
        
        prompt = gen.generate_initial_prompt()
        print(f"Generated prompt for scenario {i+1}")
        scenario_sets.append(prompt)

    # Save to CSV
    filename_prefix = f"{internal_mode}_{output_format}_{case_number}_complexity{complexity}"
    print(f"Saving to {filename_prefix}.csv")
    
    # Save with selected output format (always factor)
    try:
        with open(f'{filename_prefix}.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Scenario'])
            for scenario in scenario_sets:
                writer.writerow([scenario])
        print(f"Successfully saved to {filename_prefix}.csv")
    except Exception as e:
        print(f"Error saving to CSV: {e}")
            
    return scenario_sets

if __name__ == "__main__":
    print(f"Starting scenario generator. Python version: {sys.version}")
    parser = argparse.ArgumentParser(description='Generate legal scenario datasets with different modes.')
    parser.add_argument('--mode', choices=['non-arguable', 'reordered', 'arguable'], default='reordered',
                        help='Mode for scenario generation (default: reordered)')
    parser.add_argument('--case-number', type=int, default=10,
                        help='Number of scenarios to generate (default: 10)')
    parser.add_argument('--complexity', type=int, default=5,
                        help='Complexity level controlling the number of factors (default: 5)')
    
    args = parser.parse_args()
    # output_format is now fixed to factor
    print(f"Arguments: mode={args.mode}, output_format=factor, case_number={args.case_number}, complexity={args.complexity}")
    
    try:
        datasets = generate_datasets(
            mode=args.mode,
            case_number=args.case_number,
            complexity=args.complexity
        )
        
        print(f"Generated {args.case_number} scenarios in '{args.mode}' mode with complexity {args.complexity}.")
        print(f"Output format: factor")
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()