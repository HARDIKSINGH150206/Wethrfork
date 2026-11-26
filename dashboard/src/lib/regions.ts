/** Approximate region boxes (lat_min, lat_max, lon_min, lon_max) for the impact cards. */
export const REGIONS: { id: string; name: string; box: [number, number, number, number] }[] = [
  { id: 'kerala', name: 'Kerala', box: [8.5, 12.5, 75.5, 77.5] },
  { id: 'konkan', name: 'Konkan & Goa', box: [15.5, 20.5, 72.5, 74.5] },
  { id: 'gujarat', name: 'Gujarat', box: [20.5, 24.5, 68.5, 74.5] },
  { id: 'rajasthan', name: 'Rajasthan', box: [24.5, 30.5, 70.5, 76.5] },
  { id: 'punjab', name: 'Punjab–Haryana–Delhi', box: [28.5, 32.5, 74.5, 77.5] },
  { id: 'up', name: 'Uttar Pradesh', box: [24.5, 29.5, 78.5, 83.5] },
  { id: 'bihar', name: 'Bihar', box: [24.5, 27.5, 84.5, 87.5] },
  { id: 'wb', name: 'West Bengal', box: [22.5, 26.5, 87.5, 89.5] },
  { id: 'odisha', name: 'Odisha', box: [19.5, 22.5, 83.5, 86.5] },
  { id: 'ap', name: 'Andhra Pradesh', box: [14.5, 18.5, 78.5, 81.5] },
  { id: 'tn', name: 'Tamil Nadu', box: [8.5, 12.5, 77.5, 79.5] },
  { id: 'ne', name: 'Assam & North-East', box: [24.5, 27.5, 91.5, 95.5] },
]
