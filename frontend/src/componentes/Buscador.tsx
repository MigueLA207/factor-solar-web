import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../api/cliente'
import type { Lugar } from '../api/tipos'

interface Props {
  alElegir: (l: Lugar) => void
}

/** Combobox accesible: escribe, flechas para moverse, Enter para elegir, Esc para cerrar. */
export function Buscador({ alElegir }: Props) {
  const id = useId()
  const [texto, setTexto] = useState('')
  const [lugares, setLugares] = useState<Lugar[]>([])
  const [abierto, setAbierto] = useState(false)
  const [activo, setActivo] = useState(-1)
  const [estado, setEstado] = useState<'quieto' | 'buscando' | 'vacio' | 'error'>('quieto')
  const pedido = useRef(0)

  useEffect(() => {
    const q = texto.trim()
    if (q.length < 2) {
      setLugares([])
      setEstado('quieto')
      return
    }
    const n = ++pedido.current
    setEstado('buscando')
    const t = setTimeout(() => {
      api
        .buscar(q)
        .then((r) => {
          if (n !== pedido.current) return
          setLugares(r)
          setActivo(r.length ? 0 : -1)
          setEstado(r.length ? 'quieto' : 'vacio')
          setAbierto(true)
        })
        .catch(() => n === pedido.current && setEstado('error'))
    }, 250)
    return () => clearTimeout(t)
  }, [texto])

  const elegir = (l: Lugar) => {
    alElegir(l)
    setTexto([l.nombre, l.region].filter(Boolean).join(', '))
    setAbierto(false)
  }

  const teclas = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setAbierto(true)
      setActivo((a) => Math.min(lugares.length - 1, a + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActivo((a) => Math.max(0, a - 1))
    } else if (e.key === 'Enter' && abierto && lugares[activo]) {
      e.preventDefault()
      elegir(lugares[activo])
    } else if (e.key === 'Escape') {
      setAbierto(false)
    }
  }

  const mostrarLista = abierto && lugares.length > 0
  return (
    <div className="buscador">
      <label className="campo__rotulo" htmlFor={`${id}-q`}>
        Buscar un lugar
      </label>
      <div className="buscador__caja">
      <input
        id={`${id}-q`}
        className="campo__entrada"
        type="search"
        autoComplete="off"
        placeholder="Municipio o ciudad, p. ej. Rionegro"
        role="combobox"
        aria-expanded={mostrarLista}
        aria-controls={`${id}-lista`}
        aria-autocomplete="list"
        aria-activedescendant={mostrarLista && activo >= 0 ? `${id}-op-${activo}` : undefined}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={teclas}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        onFocus={() => lugares.length && setAbierto(true)}
      />
      <ul id={`${id}-lista`} role="listbox" className="buscador__lista" hidden={!mostrarLista}>
        {lugares.map((l, i) => (
          <li
            key={`${l.nombre}-${l.lat}-${l.lon}`}
            id={`${id}-op-${i}`}
            role="option"
            aria-selected={i === activo}
            className="buscador__opcion"
            onMouseDown={(e) => {
              e.preventDefault()
              elegir(l)
            }}
            onMouseEnter={() => setActivo(i)}
          >
            <span>{l.nombre}</span>
            <span className="buscador__region">{[l.region, l.pais].filter(Boolean).join(', ')}</span>
          </li>
        ))}
      </ul>
      </div>
      <p className="campo__nota" aria-live="polite">
        {estado === 'buscando' && 'Buscando…'}
        {estado === 'vacio' && 'Sin coincidencias. Prueba con otro nombre o haz clic en el mapa.'}
        {estado === 'error' && 'No se pudo buscar. Revisa la conexión o haz clic en el mapa.'}
      </p>
    </div>
  )
}
