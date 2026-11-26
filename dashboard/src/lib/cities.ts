/** Places drawn on the map and offered by the search box (rank 1 = shown at every zoom). */
export interface City { name: string; lat: number; lon: number; rank: 1 | 2 | 3 }
export const CITIES: City[] = [
  { name: 'New Delhi', lat: 28.61, lon: 77.21, rank: 1 }, { name: 'Mumbai', lat: 19.08, lon: 72.88, rank: 1 },
  { name: 'Kolkata', lat: 22.57, lon: 88.36, rank: 1 }, { name: 'Chennai', lat: 13.08, lon: 80.27, rank: 1 },
  { name: 'Bengaluru', lat: 12.97, lon: 77.59, rank: 1 }, { name: 'Hyderabad', lat: 17.39, lon: 78.49, rank: 1 },
  { name: 'Ahmedabad', lat: 23.02, lon: 72.57, rank: 2 }, { name: 'Pune', lat: 18.52, lon: 73.86, rank: 2 },
  { name: 'Jaipur', lat: 26.91, lon: 75.79, rank: 2 }, { name: 'Lucknow', lat: 26.85, lon: 80.95, rank: 2 },
  { name: 'Patna', lat: 25.59, lon: 85.14, rank: 2 }, { name: 'Bhopal', lat: 23.26, lon: 77.41, rank: 2 },
  { name: 'Bhubaneswar', lat: 20.3, lon: 85.82, rank: 2 }, { name: 'Guwahati', lat: 26.14, lon: 91.74, rank: 2 },
  { name: 'Thiruvananthapuram', lat: 8.52, lon: 76.94, rank: 2 }, { name: 'Kochi', lat: 9.93, lon: 76.27, rank: 3 },
  { name: 'Nagpur', lat: 21.15, lon: 79.09, rank: 2 }, { name: 'Visakhapatnam', lat: 17.69, lon: 83.22, rank: 2 },
  { name: 'Chandigarh', lat: 30.73, lon: 76.78, rank: 3 }, { name: 'Srinagar', lat: 34.08, lon: 74.8, rank: 2 },
  { name: 'Dehradun', lat: 30.32, lon: 78.03, rank: 3 }, { name: 'Varanasi', lat: 25.32, lon: 82.97, rank: 3 },
  { name: 'Ranchi', lat: 23.34, lon: 85.31, rank: 3 }, { name: 'Raipur', lat: 21.25, lon: 81.63, rank: 3 },
  { name: 'Indore', lat: 22.72, lon: 75.86, rank: 3 }, { name: 'Surat', lat: 21.17, lon: 72.83, rank: 3 },
  { name: 'Goa', lat: 15.5, lon: 73.83, rank: 3 }, { name: 'Mangaluru', lat: 12.91, lon: 74.86, rank: 3 },
  { name: 'Madurai', lat: 9.93, lon: 78.12, rank: 3 }, { name: 'Jodhpur', lat: 26.24, lon: 73.02, rank: 3 },
  { name: 'Shillong', lat: 25.58, lon: 91.89, rank: 3 }, { name: 'Imphal', lat: 24.82, lon: 93.94, rank: 3 },
  { name: 'Port Blair', lat: 11.62, lon: 92.73, rank: 3 }, { name: 'Gangtok', lat: 27.33, lon: 88.61, rank: 3 },
  { name: 'Karachi', lat: 24.86, lon: 67.0, rank: 1 }, { name: 'Lahore', lat: 31.55, lon: 74.34, rank: 2 },
  { name: 'Kathmandu', lat: 27.72, lon: 85.32, rank: 1 }, { name: 'Dhaka', lat: 23.81, lon: 90.41, rank: 1 },
  { name: 'Colombo', lat: 6.93, lon: 79.86, rank: 1 }, { name: 'Yangon', lat: 16.84, lon: 96.17, rank: 1 },
  { name: 'Thimphu', lat: 27.47, lon: 89.64, rank: 3 }, { name: 'Lhasa', lat: 29.65, lon: 91.17, rank: 2 },
]
export const SEAS: { name: string; lat: number; lon: number }[] = [
  { name: 'Arabian Sea', lat: 15, lon: 66.5 }, { name: 'Bay of Bengal', lat: 15.5, lon: 87.5 },
  { name: 'Indian Ocean', lat: 7.5, lon: 82 }, { name: 'Tibetan Plateau', lat: 33.5, lon: 86 },
]
