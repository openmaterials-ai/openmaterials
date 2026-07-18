import Mathlib.Tactic
namespace Probe
-- case: field_simp closes fully (the ZT identity shape)
theorem t1 (PF T kappa kappa_e sigma_el S : ℝ) (h_PF : PF = sigma_el * S^2)
    (h_kappa_tot : True) (hd0 : (kappa + kappa_e) ≠ 0) :
    (PF * T) / (kappa + kappa_e) = (T * sigma_el * S ^ 2) / (kappa + kappa_e) := by
  subst h_PF; field_simp <;> try ring
end Probe
