import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo } from 'react'
import { AttributionControl, MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { prefiereMenosMovimiento } from '../util/movimiento'

export interface Punto {
  lat: number
  lon: number
  nombre?: string | null
}

interface Props {
  punto: Punto
  /** Cambia cada vez que el punto llega de una búsqueda o un ejemplo: el mapa vuela hasta él. */
  vuelo: number
  alElegir: (p: Punto) => void
}

// Retícula de instrumento: dibujada en SVG, sin el pin genérico de Leaflet.
const icono = L.divIcon({
  className: 'reticula',
  html: `<svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
    <circle cx="22" cy="22" r="9" fill="none" stroke="#1d2433" stroke-width="1.5"/>
    <circle cx="22" cy="22" r="2.5" fill="#c8650c"/>
    <path d="M22 2v11M22 31v11M2 22h11M31 22h11" stroke="#1d2433" stroke-width="1.5"/>
  </svg>`,
  iconSize: [44, 44],
  iconAnchor: [22, 22],
})

function Clics({ alElegir }: { alElegir: Props['alElegir'] }) {
  useMapEvents({
    click(e) {
      alElegir({ lat: Number(e.latlng.lat.toFixed(4)), lon: Number(e.latlng.lng.toFixed(4)), nombre: null })
    },
  })
  return null
}

function Vuelo({ punto, vuelo }: { punto: Punto; vuelo: number }) {
  const mapa = useMap()
  useEffect(() => {
    if (vuelo === 0) return
    const destino: L.LatLngExpression = [punto.lat, punto.lon]
    if (prefiereMenosMovimiento()) mapa.setView(destino, 10)
    else mapa.flyTo(destino, 10, { duration: 1.1 })
    // Solo reacciona a vuelos nuevos, no a clics.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vuelo])
  return null
}

export function Mapa({ punto, vuelo, alElegir }: Props) {
  const centro = useMemo<L.LatLngExpression>(() => [punto.lat, punto.lon], [])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <MapContainer
      center={centro}
      zoom={7}
      minZoom={2}
      worldCopyJump
      className="mapa__lienzo"
      attributionControl={false}
    >
      <AttributionControl prefix='<a href="https://leafletjs.com">Leaflet</a>' />
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores de OpenStreetMap</a>'
      />
      <Marker position={[punto.lat, punto.lon]} icon={icono} keyboard={false} />
      <Clics alElegir={alElegir} />
      <Vuelo punto={punto} vuelo={vuelo} />
    </MapContainer>
  )
}
