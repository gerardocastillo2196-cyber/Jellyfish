# Statistical Bias Detection

**Agencia:** Research
**Rol Sugerido:** @data_scientist

## Objetivo de la Skill
Identifica y mitiga sesgos estadisticos comunes en analisis de datos: selection bias, confirmation bias, survivorship bias, Simpson's paradox, y otros.

## Metodologia de Razonamiento (Paso a Paso)
1. **Selection bias detection**:
   - Check if sample is truly random
   - Identify non-response patterns
2. **Confirmation bias awareness**:
   - Force testing of null hypothesis
   - Seek disconfirming evidence
3. **Survivorship bias**:
   - Look for failed cases
   - Check for companies that exited
4. **Simpson's paradox**:
   - Check for confounding variables
   - Run analysis at multiple levels
5. **Base rate fallacy**:
   - Always report base rates
   - Use Bayes' theorem
6. **Publication bias**:
   - Consider "file drawer" effect
   - Look for meta-analyses
7. **Multiple comparison correction**:
   - Bonferroni or FDR correction

## Anti-Patrones
- Assuming correlation proves causation.
- Ignoring base rates in probability statements.
- Cherry-picking favorable data points.
- HARKing (Hypothesizing After Results Known).
- Not checking assumptions of statistical tests.

## Formato de Salida Obligatorio
```markdown
# Statistical Bias Audit

**Analysis:** [Name/Description]
**Data Source:** [Dataset]

## Bias Checklist

### Selection Bias
| Check | Question | Result |
|-------|----------|--------|
| 1 | Was sample randomly selected? | ⚠️ No |
| 2 | Are there non-respondents? | ✅ Checked |

**Overall Selection Bias Assessment:** 🟡 MEDIUM RISK

### Confirmation Bias
| Check | Question | Result |
|-------|----------|--------|
| 1 | Was analysis pre-registered? | ❌ No |
| 2 | Were null hypotheses tested? | ⚠️ Partial |

## Multiple Comparisons Correction
| Test | Uncorrected p-value | Bonferroni corrected |
|------|---------------------|---------------------|
| Comparison 1 | 0.023 | 0.046 |

**Conclusion:** Only Comparison 1 remains significant after correction.
```