import { CONTROL, useStore } from '../state/store'

const tick = (ok: boolean) => (ok ? '✓' : '✗')

export function LimitsVerdict() {
  const { universes, selected, labOnline } = useStore()
  const u = universes[selected]
  if (selected === CONTROL || !u) return <section className="panel verdict"><h3>Limits verdict</h3><p className="note">Fork a universe to see the checks.</p></section>
  if (!labOnline) return <section className="panel verdict muted"><h3>Limits verdict</h3><p className="note">Lab offline: checks run in CI.</p></section>
  const v = u.verdict
  if (!v) return <section className="panel verdict"><h3>Limits verdict</h3><p className="note">computing…</p></section>
  return (
    <section className="panel verdict">
      <h3>Limits verdict</h3>
      <ul>
        <li className={v.checks.nonzero ? 'ok' : 'bad'}>{tick(v.checks.nonzero)} non-zero response</li>
        <li className={v.checks.localized ? 'ok' : 'bad'}>{tick(v.checks.localized)} localized (near {v.near_frac_day1.toFixed(2)})</li>
        <li className={v.checks.propagates ? 'ok' : 'bad'}>{tick(v.checks.propagates)} propagates (growth {v.growth_ratio.toFixed(1)}×, far {v.far_frac_max.toFixed(3)})</li>
        <li className={v.checks.stable ? 'ok' : 'bad'}>{tick(v.checks.stable)} stable (max z {v.max_z.toFixed(2)})</li>
      </ul>
      <p>OOD meter: <b className={`ood-${v.ood.level}`}>{v.ood.level}</b> ({v.ood.max_abs_z_vs_clim_std.toFixed(1)}σ)</p>
    </section>
  )
}
