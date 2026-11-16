import { useEffect, useState } from 'react'

export function prefiereMenosMovimiento() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Lleva un número desde el valor anterior hasta el final una sola vez (ease-out exponencial).
 * Solo cambia lo que se pinta durante ~700 ms; el valor final es exactamente el de la API.
 */
export function useAsentar(final: number, ms = 700) {
  const [v, setV] = useState(() => (prefiereMenosMovimiento() ? final : final * 0.9))
  useEffect(() => {
    if (prefiereMenosMovimiento()) {
      setV(final)
      return
    }
    const desde = final * 0.9
    const t0 = performance.now()
    let id = 0
    const paso = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      const e = p === 1 ? 1 : 1 - Math.pow(2, -10 * p)
      setV(desde + (final - desde) * e)
      if (p < 1) id = requestAnimationFrame(paso)
    }
    id = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(id)
  }, [final, ms])
  return v
}
