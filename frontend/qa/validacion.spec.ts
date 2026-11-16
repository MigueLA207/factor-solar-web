import { expect, test } from '@playwright/test'

// Validación de los campos de coordenadas (modo demostración, sin backend).
test('coordenadas inválidas: se limpian, se avisa y no se puede calcular', async ({ page }) => {
  await page.goto('/')
  const lat = page.getByLabel('Latitud')
  const lon = page.getByLabel('Longitud')
  const boton = page.getByRole('button', { name: /Calcular el factor/ })

  // Las letras no entran en el campo.
  await lat.fill('')
  await lat.pressSequentially('abc6,15xyz')
  await expect(lat).toHaveValue('6,15')

  // Fuera de rango: aviso y botón bloqueado.
  await lat.fill('95')
  await lat.press('Enter')
  await expect(page.getByText('La latitud va de -90 a 90.')).toBeVisible()
  await expect(lat).toHaveAttribute('aria-invalid', 'true')
  await expect(boton).toBeDisabled()

  // Vacío: aviso.
  await lat.fill('')
  await lat.press('Enter')
  await expect(page.getByText('Escribe la latitud.')).toBeVisible()

  // Formato raro (dos signos, dos comas): aviso.
  await lat.fill('6,1,5')
  await lat.press('Enter')
  await expect(page.getByText(/debe ser un número en grados decimales/)).toBeVisible()

  // Corregido: desaparece el aviso y se habilita el botón.
  await lat.fill('6,1471')
  await lon.fill('-75,3773')
  await lon.press('Enter')
  await expect(lat).not.toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByText('Corrige la latitud o la longitud')).toHaveCount(0)
})
