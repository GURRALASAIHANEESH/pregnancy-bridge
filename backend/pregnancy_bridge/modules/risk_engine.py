from typing import Dict, Optional, List


RISK_GREEN = "green"
RISK_YELLOW = "yellow"
RISK_RED = "red"


def assess_risk(
    data: Dict[str, any],
    symptoms: Optional[Dict[str, bool]] = None,
    trend_summary: Optional[Dict] = None
) -> Dict[str, any]:
    if symptoms is None:
        symptoms = {}
    
    if trend_summary is None:
        trend_summary = {}
    
    risk_score = 0
    risk_factors = []
    recommendations = []
    
    hb = data.get('hemoglobin')
    bp_sys = data.get('bp_systolic')
    bp_dia = data.get('bp_diastolic')
    ga = data.get('gestational_age')
    proteinuria = data.get('proteinuria')
    weight = data.get('weight')
    fundal_height = data.get('fundal_height')
    edema = data.get('edema')
    
    hb_score, hb_factors, hb_recs = _assess_hemoglobin(hb)
    risk_score += hb_score
    risk_factors.extend(hb_factors)
    recommendations.extend(hb_recs)
    
    bp_score, bp_factors, bp_recs = _assess_blood_pressure(bp_sys, bp_dia)
    risk_score += bp_score
    risk_factors.extend(bp_factors)
    recommendations.extend(bp_recs)
    
    protein_score, protein_factors, protein_recs = _assess_proteinuria(proteinuria)
    risk_score += protein_score
    risk_factors.extend(protein_factors)
    recommendations.extend(protein_recs)
    
    if edema:
        risk_factors.append("Edema present")
        recommendations.append("Monitor for progression, assess BP and proteinuria")
        risk_score += 1
    
    symptom_score, symptom_factors, symptom_recs = _assess_symptoms(symptoms)
    risk_score += symptom_score
    risk_factors.extend(symptom_factors)
    recommendations.extend(symptom_recs)
    
    preeclampsia_score, preeclampsia_factors, preeclampsia_recs = _assess_preeclampsia_triad(
        bp_sys, proteinuria, symptoms
    )
    risk_score += preeclampsia_score
    risk_factors.extend(preeclampsia_factors)
    recommendations.extend(preeclampsia_recs)
    
    ga_score, ga_factors, ga_recs = _assess_gestational_context(ga, hb, bp_sys)
    risk_score += ga_score
    risk_factors.extend(ga_factors)
    recommendations.extend(ga_recs)
    
    fh_score, fh_factors, fh_recs = _assess_fundal_height(fundal_height, ga)
    risk_score += fh_score
    risk_factors.extend(fh_factors)
    recommendations.extend(fh_recs)
    
    combined_score, combined_factors, combined_recs = _assess_combined_risks(hb, bp_sys)
    risk_score += combined_score
    risk_factors.extend(combined_factors)
    recommendations.extend(combined_recs)
    
    trend_score, trend_factors, trend_recs = _assess_trends(trend_summary)
    risk_score += trend_score
    risk_factors.extend(trend_factors)
    recommendations.extend(trend_recs)
    
    if risk_score >= 3:
        risk_level = RISK_RED
        summary = "HIGH RISK - Immediate referral to hospital required"
    elif risk_score >= 1:
        risk_level = RISK_YELLOW
        summary = "MODERATE RISK - Enhanced monitoring and intervention needed"
    else:
        risk_level = RISK_GREEN
        summary = "LOW RISK - Continue routine antenatal care"
    
    if not risk_factors:
        risk_factors.append("No significant risk factors identified")
    
    if not recommendations:
        recommendations.append("Continue routine ANC visits as scheduled")
        recommendations.append("Maintain balanced diet, adequate rest, and prenatal vitamins")
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "recommendations": recommendations,
        "summary": summary
    }


def _assess_trends(trend_summary: Dict) -> tuple[int, List[str], List[str]]:
    if not trend_summary:
        return 0, [], []
    
    score = 0
    factors = []
    recs = []
    
    if trend_summary.get('hb_drop'):
        magnitude = trend_summary.get('hb_drop_magnitude', 0)
        if magnitude >= 2.0:
            factors.append("CRITICAL: Severe Hb decline across visits")
            recs.append("URGENT: Transfusion evaluation required")
            recs.append("Investigate cause: bleeding, poor compliance, malabsorption")
            score += 3
        else:
            factors.append("Hb declining trend detected")
            recs.append("Intensify iron therapy, assess compliance")
            score += 2
    
    if trend_summary.get('bp_rising'):
        magnitude = trend_summary.get('bp_rise_magnitude', 0)
        if magnitude >= 20:
            factors.append("CRITICAL: Acute BP surge - Eclampsia imminent")
            recs.append("URGENT: Emergency hospital transfer")
            recs.append("Consider magnesium sulfate during transport")
            score += 3
        elif magnitude >= 15:
            factors.append("Progressive BP elevation - Pre-eclampsia developing")
            recs.append("Immediate pre-eclampsia workup")
            score += 2
        else:
            score += 1
    
    if trend_summary.get('proteinuria_worsening'):
        factors.append("Worsening proteinuria - Kidney dysfunction progressing")
        recs.append("Urgent nephrology consultation")
        recs.append("Check serum creatinine, uric acid")
        score += 2
    elif trend_summary.get('proteinuria_persistent'):
        factors.append("Persistent proteinuria across visits")
        recs.append("Monitor kidney function, consider specialist referral")
        score += 1
    
    if trend_summary.get('hb_drop') and trend_summary.get('bp_rising'):
        factors.append("CRITICAL PATTERN: Combined anemia progression + BP elevation")
        recs.append("High-risk obstetric unit required for delivery")
        score += 2
    
    if trend_summary.get('bp_rising') and trend_summary.get('proteinuria_persistent'):
        factors.append("CRITICAL PATTERN: Evolving pre-eclampsia with kidney involvement")
        recs.append("Hospital admission for fetal monitoring and maternal stabilization")
        score += 2
    
    return score, factors, recs


def _assess_hemoglobin(hb: Optional[float]) -> tuple[int, List[str], List[str]]:
    if hb is None:
        return 0, [], ["Hemoglobin not recorded - measure at next visit"]
    
    if hb < 7.0:
        return (
            3,
            [f"Severe anemia (Hb {hb} g/dL)"],
            [
                "URGENT: Immediate referral for transfusion evaluation",
                "Start oral/IV iron + folate supplementation"
            ]
        )
    elif hb < 9.0:
        return (
            2,
            [f"Moderate anemia (Hb {hb} g/dL)"],
            [
                "Start iron + folate supplementation immediately",
                "Recheck Hb in 4 weeks"
            ]
        )
    elif hb < 11.0:
        return (
            1,
            [f"Mild anemia (Hb {hb} g/dL)"],
            ["Oral iron supplementation advised"]
        )
    
    return 0, [], []


def _assess_blood_pressure(systolic: Optional[int], diastolic: Optional[int]) -> tuple[int, List[str], List[str]]:
    if systolic is None or diastolic is None:
        return 0, [], ["Blood pressure not recorded - measure at every visit"]
    
    if systolic >= 160 or diastolic >= 110:
        return (
            3,
            [f"Severe hypertension (BP {systolic}/{diastolic})"],
            [
                "URGENT: Risk of eclampsia - immediate hospital referral",
                "Check for proteinuria, headache, visual changes, right upper quadrant pain"
            ]
        )
    elif systolic >= 140 or diastolic >= 90:
        return (
            2,
            [f"Stage 2 hypertension (BP {systolic}/{diastolic})"],
            [
                "Assess for pre-eclampsia symptoms",
                "Monitor BP weekly, consider antihypertensive therapy"
            ]
        )
    elif systolic >= 130 or diastolic >= 80:
        return (
            1,
            [f"Elevated BP (BP {systolic}/{diastolic})"],
            [
                "Repeat BP measurement in 1 week",
                "Lifestyle counseling: reduce salt, adequate rest"
            ]
        )
    
    return 0, [], []


def _assess_proteinuria(proteinuria: Optional[str]) -> tuple[int, List[str], List[str]]:
    if not proteinuria:
        return 0, [], []
    
    protein_level = proteinuria.lower()
    
    if any(x in protein_level for x in ['3+', '4+', '3plus', '4plus']):
        return (
            3,
            [f"Severe proteinuria ({proteinuria})"],
            ["High risk for pre-eclampsia - immediate evaluation"]
        )
    elif any(x in protein_level for x in ['1+', '2+', 'trace']):
        return (
            1,
            [f"Proteinuria detected ({proteinuria})"],
            ["Recheck urine protein, monitor for pre-eclampsia"]
        )
    
    return 0, [], []


def _assess_symptoms(symptoms: Dict[str, bool]) -> tuple[int, List[str], List[str]]:
    preeclampsia_symptoms = []
    
    if symptoms.get("headache"):
        preeclampsia_symptoms.append("headache")
    if symptoms.get("visual_changes") or symptoms.get("blurred_vision"):
        preeclampsia_symptoms.append("visual changes")
    if symptoms.get("nausea") or symptoms.get("vomiting"):
        preeclampsia_symptoms.append("nausea/vomiting")
    if symptoms.get("swelling") or symptoms.get("edema"):
        preeclampsia_symptoms.append("swelling")
    if symptoms.get("abdominal_pain") or symptoms.get("epigastric_pain"):
        preeclampsia_symptoms.append("abdominal pain")
    
    if not preeclampsia_symptoms:
        return 0, [], []
    
    return (
        1,
        [f"Pre-eclampsia symptoms: {', '.join(preeclampsia_symptoms)}"],
        ["Screen for pre-eclampsia (BP, proteinuria, liver/kidney function)"]
    )


def _assess_preeclampsia_triad(
    bp_systolic: Optional[int],
    proteinuria: Optional[str],
    symptoms: Dict[str, bool]
) -> tuple[int, List[str], List[str]]:
    has_hypertension = bp_systolic and bp_systolic >= 140
    has_proteinuria = proteinuria and proteinuria not in ['negative', 'nil', 'trace']
    
    symptom_count = sum([
        symptoms.get("headache", False),
        symptoms.get("visual_changes", False),
        symptoms.get("swelling", False)
    ])
    has_symptoms = symptom_count >= 2
    
    if has_hypertension and has_proteinuria:
        return (
            3,
            ["PRE-ECLAMPSIA LIKELY: Hypertension + Proteinuria"],
            [
                "URGENT: Immediate referral to hospital for pre-eclampsia workup",
                "Consider magnesium sulfate prophylaxis, monitor for eclampsia"
            ]
        )
    elif has_hypertension and has_symptoms:
        return (
            2,
            ["Pre-eclampsia risk: Hypertension + Symptoms"],
            ["Urgent urine protein test, refer if positive"]
        )
    
    return 0, [], []


def _assess_gestational_context(
    ga: Optional[int],
    hb: Optional[float],
    bp_systolic: Optional[int]
) -> tuple[int, List[str], List[str]]:
    if ga is None:
        return 0, [], []
    
    score = 0
    factors = []
    recs = []
    
    if ga >= 37:
        if hb and hb < 10.0:
            factors.append("Anemia at term increases labor complications")
            score += 1
        if bp_systolic and bp_systolic >= 140:
            factors.append("Hypertension at term - delivery may be indicated")
            recs.append("Discuss timing of delivery with obstetrician")
            score += 1
    elif ga >= 34:
        recs.append("Late preterm - monitor for preterm labor signs")
    elif ga < 28:
        recs.append("Early pregnancy - ensure adequate nutrition, rest, and iron supplementation")
    
    return score, factors, recs


def _assess_fundal_height(fundal_height: Optional[int], ga: Optional[int]) -> tuple[int, List[str], List[str]]:
    if not fundal_height or not ga:
        return 0, [], []
    
    expected_fh = ga
    difference = abs(fundal_height - expected_fh)
    
    if difference <= 3:
        return 0, [], []
    
    if fundal_height < expected_fh:
        return (
            1,
            [f"Fundal height below expected (FH {fundal_height}cm at {ga}wks)"],
            ["Consider ultrasound for IUGR (intrauterine growth restriction)"]
        )
    else:
        return (
            1,
            [f"Fundal height above expected (FH {fundal_height}cm at {ga}wks)"],
            ["Consider ultrasound for polyhydramnios or macrosomia"]
        )


def _assess_combined_risks(hb: Optional[float], bp_systolic: Optional[int]) -> tuple[int, List[str], List[str]]:
    if hb and hb < 9.0 and bp_systolic and bp_systolic >= 140:
        return (
            1,
            ["Combined anemia + hypertension increases maternal morbidity"],
            ["Hospital delivery with high-risk obstetric care recommended"]
        )
    
    return 0, [], []
