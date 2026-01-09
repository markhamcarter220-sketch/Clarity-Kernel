"""
Example 06: W-Counting Fraud Detection (Anti-Patterns)

This example demonstrates:
- Why w ≤ 3 enforcement is critical for safety
- Illegal patterns that attempt to game w-counting
- How the kernel mechanically detects fraud
- Correct approaches to handle w > 3

The w ≤ 3 constraint is a HARD LIMIT on reasoning complexity.
Gaming this constraint through bundling, misclassification, or guessing
is security fraud that undermines the entire safety guarantee.
"""

from clarity_kernel import (
    Variable,
    WCountingFraudViolation,
    ComplexityInvariantViolation,
    detect_variable_bundling,
    detect_probabilistic_collapse,
    validate_material_classification,
    validate_complexity,
)


def print_section(title: str):
    """Print section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def demonstrate_honest_w_counting():
    """Shows correct w-counting with honest variable classification."""
    print_section("HONEST W-COUNTING (BASELINE)")

    print("\nScenario: Medical dosage calculation")
    print("Required information:")
    print("  1. dosage_mg (material, unresolved)")
    print("  2. patient_weight_kg (material, unresolved)")
    print("  3. administration_route (material, unresolved)")
    print("  4. drug_name (material, resolved)")
    print("  5. request_id (non-material, for logging only)")

    variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("patient_weight_kg", resolved=False, material=True, value=None),
        Variable("administration_route", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=True, material=True, value="aspirin"),
        Variable("request_id", resolved=True, material=False, value="req_12345"),
    ]

    w = validate_complexity(variables, max_width=3)

    print(f"\n✓ Measured w = {w} (3 unresolved material variables)")
    print("✓ Passes w ≤ 3 constraint")
    print("✓ Honest classification - all safety-critical vars marked material")


def demonstrate_fraud_pattern_1_variable_bundling():
    """
    FRAUD PATTERN #1: Variable Bundling

    Attacker bundles multiple material concerns into one variable to artificially
    reduce w.
    """
    print_section("FRAUD PATTERN #1: VARIABLE BUNDLING")

    print("\n⚠ FRAUDULENT APPROACH:")
    print("Instead of 4 separate variables (w=4 → STOP required):")
    print("  - dosage_mg")
    print("  - patient_weight_kg")
    print("  - administration_route")
    print("  - drug_name")
    print("\nAttacker creates ONE bundled variable (w=1 → fraudulently passes):")
    print("  - patient_config_and_dosage")

    fraudulent_variables = [
        Variable(
            "patient_config_and_dosage",  # FRAUD: Bundles 4 concerns
            resolved=False,
            material=True,
            value=None
        ),
    ]

    print("\n🔍 Kernel Detection:")
    fraud = detect_variable_bundling(fraudulent_variables)

    if fraud:
        print(f"✓ FRAUD DETECTED: {fraud.fraud_type}")
        print(f"  Variable: {fraud.evidence['variable_name']}")
        print(f"  Pattern: {fraud.evidence['pattern']}")
        print(f"  Message: {str(fraud)[:80]}...")

    print("\n✓ CORRECT APPROACH:")
    print("Split into separate material variables:")

    correct_variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("patient_weight_kg", resolved=False, material=True, value=None),
        Variable("administration_route", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),
    ]

    print(f"  Variables: {', '.join(v.name for v in correct_variables)}")
    print("  Measured w = 4 (exceeds limit)")
    print("  Kernel response: STOP or DECOMPOSE")
    print("  Required action: Break down request or get explicit values")

    try:
        validate_complexity(correct_variables, max_width=3)
    except ComplexityInvariantViolation as e:
        print(f"\n✓ Complexity violation raised (as expected):")
        print(f"  w = {e.measured_w}")
        print(f"  Unresolved: {', '.join(e.unresolved_variables)}")


def demonstrate_fraud_pattern_2_generic_names():
    """
    FRAUD PATTERN #2: Generic Variable Names

    Using overly generic names like "config", "data", "options" to hide bundled
    concerns.
    """
    print_section("FRAUD PATTERN #2: GENERIC VARIABLE NAMES")

    print("\n⚠ FRAUDULENT APPROACH:")
    print("Using generic name to hide multiple concerns:")

    fraudulent_variables = [
        Variable("config", resolved=False, material=True, value=None),  # FRAUD
    ]

    print("\n🔍 Kernel Detection:")
    fraud = detect_variable_bundling(fraudulent_variables)

    if fraud:
        print(f"✓ FRAUD DETECTED: {fraud.fraud_type}")
        print(f"  Variable: {fraud.evidence['variable_name']}")
        print(f"  Message: Generic variable name 'config' may hide bundled concerns")

    print("\n✓ CORRECT APPROACH:")
    print("Use specific, single-purpose variable names:")

    correct_variables = [
        Variable("max_retries", resolved=False, material=True, value=None),
        Variable("timeout_seconds", resolved=False, material=True, value=None),
        Variable("target_endpoint", resolved=True, material=True, value="/api/users"),
    ]

    print(f"  Variables: {', '.join(v.name for v in correct_variables)}")
    print("  Each name describes a single, specific concern")


def demonstrate_fraud_pattern_3_dict_bundling():
    """
    FRAUD PATTERN #3: Dictionary Bundling

    Resolved variable contains a dict with multiple material keys, hiding complexity.
    """
    print_section("FRAUD PATTERN #3: DICTIONARY BUNDLING")

    print("\n⚠ FRAUDULENT APPROACH:")
    print("Single variable containing multi-key dict:")

    fraudulent_variables = [
        Variable(
            "patient_data",
            resolved=True,
            material=True,
            value={
                "age": 65,
                "weight": 70,
                "blood_pressure": "120/80",
                "medications": ["aspirin", "lisinopril"]
            }
        ),
    ]

    print(f"  Variable: patient_data")
    print(f"  Dict keys: {list(fraudulent_variables[0].value.keys())}")
    print("  Hides 4 separate material concerns in one variable")

    print("\n🔍 Kernel Detection:")
    fraud = detect_variable_bundling(fraudulent_variables)

    if fraud:
        print(f"✓ FRAUD DETECTED: {fraud.fraud_type}")
        print(f"  Num keys: {fraud.evidence['num_keys']}")
        print(f"  Keys: {fraud.evidence['keys']}")

    print("\n✓ CORRECT APPROACH:")
    print("Separate variable for each material concern:")

    correct_variables = [
        Variable("patient_age", resolved=True, material=True, value=65),
        Variable("patient_weight_kg", resolved=True, material=True, value=70),
        Variable("blood_pressure", resolved=True, material=True, value="120/80"),
        Variable("current_medications", resolved=True, material=True, value=["aspirin", "lisinopril"]),
    ]

    print(f"  Variables: {', '.join(v.name for v in correct_variables)}")


def demonstrate_fraud_pattern_4_probabilistic_collapse():
    """
    FRAUD PATTERN #4: Probabilistic Collapse

    Guessing/inferring values to artificially reduce w, violating I-6 (Silence).
    """
    print_section("FRAUD PATTERN #4: PROBABILISTIC COLLAPSE")

    print("\n⚠ FRAUDULENT APPROACH:")
    print("Initial state: w=3 (at limit)")

    variables_before = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
        Variable("frequency", resolved=False, material=True, value=None),
    ]

    print("  dosage_mg: unresolved")
    print("  route: unresolved")
    print("  frequency: unresolved")
    print("  Measured w = 3 ✓")

    print("\nAttacker wants to add 4th variable (drug_name) but w would become 4 (STOP)")
    print("Fraudulent solution: GUESS values to reduce w:")

    variables_after = [
        Variable("dosage_mg", resolved=True, material=True, value=50),  # GUESSED "standard dose"
        Variable("route", resolved=True, material=True, value="oral"),  # GUESSED "most common"
        Variable("frequency", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),  # Now can add without exceeding
    ]

    print("  dosage_mg: GUESSED → 50 (\"standard dose\")")
    print("  route: GUESSED → oral (\"most common\")")
    print("  frequency: unresolved")
    print("  drug_name: unresolved (new variable)")
    print("  Reported w = 2 (fraudulent)")

    print("\n🔍 Kernel Detection:")
    fraud = detect_probabilistic_collapse(variables_before, variables_after)

    if fraud:
        print(f"✓ FRAUD DETECTED: {fraud.fraud_type}")
        print(f"  Actual w (before guessing): {fraud.evidence['actual_w']}")
        print(f"  Reported w (after guessing): {fraud.evidence['reported_w']}")
        print(f"  Collapsed variables: {[v['name'] for v in fraud.evidence['collapsed_variables']]}")

    print("\n✓ CORRECT APPROACH:")
    print("If w would exceed 3 after adding variable:")
    print("  1. STOP and request explicit values")
    print("  2. DECOMPOSE into smaller sub-requests")
    print("  3. Escalate to human-in-the-loop")
    print("  NEVER guess to artificially reduce w")


def demonstrate_fraud_pattern_5_material_misclassification():
    """
    FRAUD PATTERN #5: Material Misclassification

    Marking safety-critical variables as non-material to bypass w ≤ 3.
    """
    print_section("FRAUD PATTERN #5: MATERIAL MISCLASSIFICATION")

    print("\n⚠ FRAUDULENT APPROACH:")
    print("Scenario: Medical device dosage control")
    print("True material variables: dosage, drug, patient_id, route (w=4)")
    print("\nFraudulent classification to pass w≤3:")

    fraudulent_variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),  # Honest
        Variable("patient_id", resolved=False, material=True, value=None),  # Honest
        Variable("drug_name", resolved=False, material=False, value=None),  # FRAUD: Should be material
        Variable("route", resolved=False, material=False, value=None),  # FRAUD: Should be material
    ]

    print("  dosage_mg: material=True ✓")
    print("  patient_id: material=True ✓")
    print("  drug_name: material=FALSE ✗ (FRAUD - actually safety-critical)")
    print("  route: material=FALSE ✗ (FRAUD - actually safety-critical)")
    print("  Fraudulent w = 2 (passes constraint)")

    print("\n🔍 Kernel Detection:")
    safety_critical_names = {"dosage_mg", "patient_id", "drug_name", "route"}

    try:
        validate_material_classification(fraudulent_variables, safety_critical_names)
    except WCountingFraudViolation as e:
        print(f"✓ FRAUD DETECTED: {e.fraud_type}")
        print(f"  Variable: {e.evidence['variable_name']}")
        print(f"  Marked as: material={e.evidence['marked_material']}")
        print(f"  Should be: material={e.evidence['should_be_material']}")

    print("\n✓ CORRECT APPROACH:")
    print("Honest classification:")

    correct_variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),  # Honest
        Variable("route", resolved=False, material=True, value=None),  # Honest
    ]

    print("  All safety-critical variables: material=True")
    print("  Honest w = 4 (exceeds limit)")
    print("  Kernel response: STOP or DECOMPOSE (as required)")


def demonstrate_legitimate_decomposition():
    """
    Shows the CORRECT way to handle w > 3: decomposition.
    """
    print_section("CORRECT APPROACH: DECOMPOSITION")

    print("\nWhen w > 3, legitimate options:")
    print("  1. DECOMPOSE into smaller requests")
    print("  2. Request explicit values from user")
    print("  3. Escalate to human-in-the-loop")

    print("\n✓ Example: Medical Prescription (w=4 → decompose)")
    print("\nOriginal request (w=4 - too complex):")

    original_variables = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
    ]

    print(f"  Variables: {[v.name for v in original_variables]}")
    print("  w = 4 → EXCEEDS LIMIT")

    print("\nDecomposed into 2 sub-requests:")
    print("\nSub-request 1: Patient Identification (w=1)")

    sub_request_1 = [
        Variable("patient_id", resolved=False, material=True, value=None),
    ]

    w1 = validate_complexity(sub_request_1, max_width=3)
    print(f"  Variables: patient_id")
    print(f"  w = {w1} ✓")

    print("\nSub-request 2: Prescription Details (w=3)")
    print("  (After patient_id resolved from sub-request 1)")

    sub_request_2 = [
        Variable("dosage_mg", resolved=False, material=True, value=None),
        Variable("drug_name", resolved=False, material=True, value=None),
        Variable("route", resolved=False, material=True, value=None),
        Variable("patient_id", resolved=True, material=True, value="P12345"),  # From sub-request 1
    ]

    w2 = validate_complexity(sub_request_2, max_width=3)
    print(f"  Variables: dosage_mg, drug_name, route")
    print(f"  w = {w2} ✓")

    print("\n✓ Both sub-requests satisfy w ≤ 3")
    print("✓ No fraud - honest decomposition")


def main():
    print("=" * 70)
    print("Example 06: W-Counting Fraud Detection")
    print("=" * 70)
    print("\nDemonstrating mechanical detection of w-counting fraud")

    demonstrate_honest_w_counting()
    demonstrate_fraud_pattern_1_variable_bundling()
    demonstrate_fraud_pattern_2_generic_names()
    demonstrate_fraud_pattern_3_dict_bundling()
    demonstrate_fraud_pattern_4_probabilistic_collapse()
    demonstrate_fraud_pattern_5_material_misclassification()
    demonstrate_legitimate_decomposition()

    print("\n" + "=" * 70)
    print("KEY PRINCIPLES")
    print("=" * 70)
    print("\n1. W-counting is deterministic and ungameable")
    print("   w := count(variables WHERE resolved=FALSE AND material=TRUE)")

    print("\n2. Material variables MUST be honestly classified")
    print("   Misclassification is security fraud, not convenience")

    print("\n3. Variable bundling is forbidden")
    print("   Each material concern = separate variable")

    print("\n4. Probabilistic collapse violates I-6 (Silence)")
    print("   Cannot guess values to reduce w")

    print("\n5. When w > 3, legitimate options only:")
    print("   - DECOMPOSE into smaller requests")
    print("   - Request explicit values")
    print("   - Escalate to HIL")
    print("   NEVER: Bundle, misclassify, or guess")

    print("\n6. Fraud detection is mechanical, not rhetorical")
    print("   Heuristics detect common gaming patterns")


if __name__ == "__main__":
    main()
