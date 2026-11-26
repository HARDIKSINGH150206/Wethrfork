export function About() {
  return (
    <div className="page narrow">
      <div className="pagehead"><div><h2>About Wethrfork</h2><p>A weather model with a speed limit: a hybrid forecasting system for India that forks into alternate universes when you shock it.</p></div></div>
      <div className="cards2">
        <section className="card">
          <h3>How it works</h3>
          <ol className="steps">
            <li><b>Skill head.</b> A per-cell ridge regression and a small neural network, blended per lead day and calibrated, give the best forecast we can make.</li>
            <li><b>Dynamics head.</b> A second network of the same design turns a shock into a response. Its change is added around the forecast: a control forecast plus a perturbation model.</li>
            <li><b>Speed limit.</b> Each daily step is a bounded wind-driven advection (at most 4 cells) followed by three 3×3 convolutions (3 cells), plus 1 for interpolation: the update reaches at most 8 cells along either axis (about 900 km; up to 9.7 cells diagonally) per day. There is no attention, pooling, global normalisation or U-Net. Unit tests check the bound; it limits where a change can appear, not whether it is physically right.</li>
            <li><b>Always valid.</b> A final clamp after the delta keeps rain and moisture non-negative and temperature physical. A zero shock skips the shocked run, so it changes nothing, bit for bit.</li>
          </ol>
        </section>
        <section className="card">
          <h3>Model card</h3>
          <table className="kv"><tbody>
            <tr><td>Grid</td><td>32 × 36 cells of 1°, 6.5–37.5°N, 65.5–100.5°E</td></tr>
            <tr><td>Channels</td><td>t2m, tp, u10, v10, msl, tcwv (daily)</td></tr>
            <tr><td>Input</td><td>3 days of physical fields, the day of year</td></tr>
            <tr><td>Output</td><td>1–14 days; the dashboard uses 10</td></tr>
            <tr><td>Parameters</td><td>about 0.39 M per network, two networks plus the ridge</td></tr>
            <tr><td>Hardware</td><td>CPU, 4 threads, offline; a shocked 10-day call takes about 0.2 s</td></tr>
            <tr><td>Training data</td><td>modified ERA5 reanalysis (Hersbach et al., 2020; Copernicus Climate Change Service) via Google WeatherBench 2, CC BY 4.0</td></tr>
            <tr><td>Splits</td><td>trained 2005–2019, calibrated on 2020, graded on 2021</td></tr>
          </tbody></table>
        </section>
      </div>
      <section className="card wide">
        <h3>Known limits</h3>
        <ul className="limits">
          <li><b>Jet transport.</b> The Arabian Sea low-level jet (12–15 m/s) is faster than our 4-cell advection cap.</li>
          <li><b>Learned, not proven.</b> Locality of a response is bounded by design and tested; sign and size are learned from data. A shock sent through the API is also not the same as adding it to the last input day and forecasting normally: the forecast stays that of the unshocked state and the response is added (largest rainfall gap over 71 held-out windows: median 14.5 mm/day, up to 105). A monsoon stall first dries the west coast, then raises rain from day 4: the same sequence seen after naturally weak monsoon flow, so a correlation and not a verified intervention effect.</li>
          <li><b>Resolution.</b> 1° daily fields cannot hold a cyclone core, and energy that leaves the domain is lost.</li>
          <li><b>Long leads.</b> Beyond about a week the skill head is close to climatology by design.</li>
          <li><b>Impact.</b> Regional cards show mean change over land cells. They are not probabilities.</li>
        </ul>
      </section>
    </div>
  )
}
