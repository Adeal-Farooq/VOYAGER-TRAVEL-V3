export function getModeIcon(mode: string): string {
  const icons: Record<string, string> = {
    walk: '🚶',
    walk_to_bus: '🚶➡️🚌',
    walk_to_metro: '🚶➡️🚇',
    walk_from_bus: '🚌➡️🚶',
    walk_from_metro: '🚇➡️🚶',
    bus_ordinary: '🚌',
    bus_ac_vajra: '🚍',
    metro: '🚇',
    metro_interchange: '🔀🚇',
    car: '🚗',
    bike: '🏍️',
    auto: '🛺',
    cab: '🚕',
    cab_xl: '🚐',
    cab_women: '👩‍🚕',
    cab_pet: '🐾🚕',
    cab_economy: '🚕',
    cab_premium: '🚙',
    bike_taxi: '🏍️',
    interchange: '🔄',
    driving: '🚗',
    kia_bus: '🚍',
    bus_to_metro: '🚌➡️🚇',
    metro_to_bus: '🚇➡️🚌',
    bus_then_cab: '🚌➡️🚕',
    train: '🚆',
  }
  return icons[mode] || '📍'
}

export function getModeLabel(mode: string): string {
  const labels: Record<string, string> = {
    walk: 'Walk',
    walk_to_bus: 'Walk to Bus Stop',
    walk_to_metro: 'Walk to Metro',
    walk_from_bus: 'Walk from Bus Stop',
    walk_from_metro: 'Walk from Metro',
    bus_ordinary: 'BMTC Ordinary Bus',
    bus_ac_vajra: 'BMTC AC Vajra',
    metro: 'Namma Metro',
    metro_interchange: 'Metro (Interchange)',
    car: 'Personal Car',
    bike: 'Bike',
    auto: 'Auto',
    cab: 'Cab',
    cab_xl: 'Cab XL',
    cab_women: 'Cab for Women',
    cab_pet: 'Cab Pet',
    cab_economy: 'Cab Economy',
    cab_premium: 'Cab Premium',
    bike_taxi: 'Bike Taxi',
    interchange: 'Interchange',
    driving: 'Driving',
    kia_bus: 'KIA Vayu Vajra',
    bus_to_metro: 'Bus → Metro',
    metro_to_bus: 'Metro → Bus',
    bus_then_cab: 'Bus + Cab',
    train: 'Train',
  }
  return labels[mode] || mode
}

export function getPlaceIcon(placeType: string, isRecommended: boolean): string {
  if (!isRecommended) return '⬜'
  const icons: Record<string, string> = {
    malls: '🛍️',
    hospitals: '🏥',
    airport: '✈️',
    railway_stations: '🚉',
    bus_stands: '🚏',
    parks: '🌳',
    it_hubs: '🏢',
    metro_stations: '🚇',
    bus_stops: '🚏',
    atm: '🏧',
    bank: '🏦',
    restaurant: '🍽️',
    hotel: '🏨',
    temple: '🛕',
    school: '📚',
    petrol_pump: '⛽',
  }
  return icons[placeType] || '📍'
}

export function formatDuration(minutes: number): string {
  if (!minutes || minutes < 0) return '0 min'
  if (minutes < 60) return `${Math.round(minutes)} min`
  const hours = Math.floor(minutes / 60)
  const mins = Math.round(minutes % 60)
  return `${hours}h ${mins}m`
}

export function formatRupees(amount: number): string {
  if (!amount && amount !== 0) return '₹0'
  return `₹${amount.toFixed(2)}`
}

export function getScoreColor(score: number): string {
  if (score >= 80) return '#22c55e'
  if (score >= 60) return '#eab308'
  if (score >= 40) return '#f97316'
  return '#ef4444'
}

export function getScoreLabel(score: number): string {
  if (score >= 80) return 'Excellent'
  if (score >= 70) return 'Good'
  if (score >= 60) return 'Fair'
  if (score >= 40) return 'Poor'
  return 'Avoid'
}

export function getModeIconName(mode: string): string {
  const map: Record<string, string> = {
    walk: 'directions_walk',
    bus_ordinary: 'directions_bus',
    bus_ac_vajra: 'airport_shuttle',
    metro: 'subway',
    metro_interchange: 'transfer_within_a_station',
    car: 'directions_car',
    bike: 'pedal_bike',
    auto: 'local_taxi',
    cab: 'local_taxi',
    cab_xl: 'van',
    cab_women: 'female',
    cab_pet: 'pets',
    bike_taxi: 'pedal_bike',
    interchange: 'sync_alt',
    driving: 'directions_car',
    kia_bus: 'airport_shuttle',
    train: 'train',
    bus_to_metro: 'directions_bus',
    metro_to_bus: 'subway',
  }
  return map[mode] || 'directions_transit'
}

export function getPlaceIconName(placeType: string): string {
  const map: Record<string, string> = {
    mall: 'local_mall',
    hospital: 'local_hospital',
    clinic: 'local_hospital',
    airport: 'flight',
    railway_station: 'train',
    bus_stop: 'directions_bus',
    bus_stand: 'directions_bus',
    park: 'park',
    it_hub: 'business_center',
    metro_station: 'subway',
    atm: 'account_balance',
    bank: 'account_balance',
    restaurant: 'restaurant',
    cafe: 'local_cafe',
    hotel: 'hotel',
    lodge: 'lodging',
    temple: 'temple_hindu',
    mosque: 'mosque',
    church: 'church',
    school: 'school',
    college: 'school',
    university: 'school',
    petrol_pump: 'local_gas_station',
    charging_station: 'ev_station',
    police_station: 'local_police',
    pharmacy: 'local_pharmacy',
    supermarket: 'local_grocery_store',
    gym: 'fitness_center',
    library: 'local_library',
    cinema: 'theater_comedy',
    post_office: 'mark_as_unread',
  }
  return map[placeType] || 'location_on'
}
