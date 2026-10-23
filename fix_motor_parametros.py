with open('C:\\Users\\USUARIO\\Desktop\\Desarrollo-Creditos\\backend\\services\\motor_parametros.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the specific issues
content = content.replace(
    'capacidad_pago_limite_ingresos_pct: Decimal = Decimal("85")',
    'capacidad_pago_limite_ingresos_pct: Decimal = Decimal("0.85")'
)

content = content.replace(
    'if self.capacidad_pago_factor_macro > self.capacidad_pago_pct_region_nacional / Decimal("100"):',
    'if self.capacidad_pago_factor_macro > Decimal("1.0"):'
)

content = content.replace(
    'errores.append("capacidad_pago_factor_macro no debe exceder el factor regional nacional")',
    'errores.append("capacidad_pago_factor_macro no debe exceder 1.0")'
)

# Write back
with open('C:\\Users\\USUARIO\\Desktop\\Desarrollo-Creditos\\backend\\services\\motor_parametros.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('File fixed successfully!')