INSERT INTO rol (nombre, descripcion) VALUES
    ('cliente', 'Usuario solicitante'),
    ('asesor', 'Asesor comercial'),
    ('aliado', 'Usuario de aliado comercial'),
    ('admin', 'Administrador de la plataforma'),
    ('contabilidad', 'Usuario de contabilidad'),
    ('concesionario', 'Administrador de sede: ve y opera todas las solicitudes de su concesionario y gestiona sus asesores')
ON CONFLICT (nombre) DO NOTHING;



INSERT INTO aliado_financiero (nit, nombre, tipo, es_propio, activo)
VALUES ('814005081', 'INVERSIONES PACIFICO S.A.', 'otro', TRUE, TRUE)
ON CONFLICT (nit) DO NOTHING;

UPDATE aliado_financiero
SET es_propio = TRUE
WHERE nit = '814005081';

INSERT INTO concesionario (nombre) VALUES
    ('TULUA MOTOS SA'),
    ('SUMOTO SA PALMIRA'),
    ('PIJAOS MOTOS S.A')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO aliado_concesionario (id_aliado, id_concesionario)
SELECT a.id_aliado, c.id_concesionario
FROM aliado_financiero a
CROSS JOIN concesionario c
WHERE a.nit = '814005081'
    AND c.nombre IN ('TULUA MOTOS SA', 'SUMOTO SA PALMIRA', 'PIJAOS MOTOS S.A')
ON CONFLICT (id_aliado, id_concesionario) DO NOTHING;

INSERT INTO banco (codigo_ach, nombre, nit, activo) VALUES
    ('007', 'BANCOLOMBIA', '890903938', TRUE),
    ('009', 'BANCO DE BOGOTA', '860002964', TRUE),
    ('012', 'BBVA COLOMBIA', '860003020', TRUE),
    ('013', 'BANCO DAVIVIENDA', '860034313', TRUE),
    ('023', 'BANCO DE OCCIDENTE', '890300279', TRUE),
    ('051', 'BANCO AV VILLAS', '860007336', TRUE),
    ('052', 'BANCO CAJA SOCIAL', '860007338', TRUE),
    ('100', 'BANCO W', '900091362', TRUE),
    ('102', 'BANCO UNION', '890200486', TRUE)
ON CONFLICT (codigo_ach) DO NOTHING;

INSERT INTO cuenta_bancaria (id_banco, tipo, numero, titular, nit_titular, id_aliado, activa)
SELECT b.id_banco, 'ahorros', '0000000000', 'INVERSIONES PACIFICO S.A.',
       '814005081', a.id_aliado, TRUE
FROM banco b, aliado_financiero a
WHERE b.codigo_ach = '007'
    AND a.nit = '814005081'
ON CONFLICT (id_banco, numero, tipo) DO NOTHING;

INSERT INTO cuenta_bancaria (id_banco, tipo, numero, titular, id_concesionario, activa)
-- TODO: reemplazar los números de cuenta ficticios por cuentas reales antes de producción.
SELECT b.id_banco, 'ahorros', c.nombre || '-CTA', c.nombre, c.id_concesionario, TRUE
FROM banco b, concesionario c
WHERE b.codigo_ach = '007'
    AND c.nombre IN ('TULUA MOTOS SA', 'SUMOTO SA PALMIRA', 'PIJAOS MOTOS S.A')
ON CONFLICT (id_banco, numero, tipo) DO NOTHING;

INSERT INTO aliado_producto (id_aliado, nombre, activo)
SELECT id_aliado, 'Financiacion de motocicleta', TRUE
FROM aliado_financiero
WHERE nit = '814005081'
ON CONFLICT (id_aliado, nombre) DO NOTHING;

-- Parametros comerciales del producto propio (alineados con la politica:
-- plazo 12-48 meses, monto $500.000 - $20.000.000, tasa de referencia 1,85 % m.v.)
UPDATE aliado_producto
SET tasa_min = 1.5,
    tasa_max = 2.2,
    plazo_min_meses = 12,
    plazo_max_meses = 48,
    monto_min = 500000,
    monto_max = 20000000
WHERE nombre = 'Financiacion de motocicleta'
  AND id_aliado = (SELECT id_aliado FROM aliado_financiero WHERE nit = '814005081');

-- Seguro de vida deudores incluido en la cuota. Prima vigente del
-- negocio: 0,35 % mensual sobre el saldo financiado
-- (cuota_seguro = saldo * 0,35 %; valor_seguro_vida = prima * plazo).
INSERT INTO aseguradora (nit, nombre, activa) VALUES
    ('999999999', 'ASEGURADORA ALIADA', TRUE)
ON CONFLICT (nit) DO NOTHING;

INSERT INTO seguro_producto (id_aseguradora, tipo, nombre, descripcion, vigencia_meses, tasa_prima, activo)
SELECT id_aseguradora, 'vida_decreciente', 'Seguro de vida deudores',
       'Cubre el saldo insoluto de la deuda', 60, 0.35, TRUE
FROM aseguradora
WHERE nit = '999999999'
ON CONFLICT (id_aseguradora, tipo, nombre) DO NOTHING;

-- Catalogo de causales del motor de decision (PPT v4 + BRD).
-- R* = rechazo, RC* = requiere codeudor, E* = estudio (decision interna).
INSERT INTO criterio_evaluacion (codigo, descripcion, tipo) VALUES
    ('R1',  'Clientes reportados como fallecidos', 'buro'),
    ('R2',  'Embargos vigentes', 'buro'),
    ('R3',  'Cancelaciones por mal habito', 'buro'),
    ('R4',  'Cartera castigada', 'buro'),
    ('R5',  'Dudoso recaudo', 'buro'),
    ('R6',  'Mora 60 dias o mas vigentes', 'buro'),
    ('R7',  'Mora historica 30 dias', 'buro'),
    ('R8',  'Mora historica 60 dias', 'buro'),
    ('R9',  'Mora historica 90 dias o mas', 'buro'),
    ('R10', 'Calificacion diferente A y B', 'buro'),
    ('R11', 'Reestructuracion', 'buro'),
    ('R12', 'Documento no vigente', 'buro'),
    ('R13', 'No cumple politica de edad', 'interno'),
    ('R14', 'Score por debajo del punto de corte', 'buro'),
    ('R15', 'Ingresos por debajo del permitido', 'interno'),
    ('R16', 'No tiene Camara de Comercio', 'interno'),
    ('R17', 'Endeudamiento mayor a 90 por ciento', 'buro'),
    ('R18', 'Sin disponible', 'interno'),
    ('R19', 'Sin capacidad de pago', 'interno'),
    ('R20', 'Informacion insuficiente para aprobar', 'interno'),
    ('R21', 'Nacionalidad diferente a colombiana', 'interno'),
    ('R22', 'Multas en el RUNT', 'interno'),
    ('R23', 'Cliente sin experiencia crediticia', 'buro'),
    ('R24', 'No cumple anos minimos de Camara de Comercio', 'interno'),
    ('R25', 'Perfil Score D', 'buro'),
    ('RC1', 'No cumple continuidad', 'interno'),
    ('RC2', 'Perfil Score D (requiere codeudor)', 'buro'),
    ('RC3', 'Validacion de exclusiones (requiere codeudor)', 'buro'),
    ('RC4', 'Ingreso en zona gris para independiente', 'interno'),
    ('E1', 'Clientes diferentes a persona natural', 'interno'),
    ('E2', 'Mora 30 dias vigentes', 'buro'),
    ('E3', 'Sin valor ingreso y quanto fin', 'interno'),
    ('E4', 'Perfil ingreso bajo', 'interno'),
    ('E5', 'Perfil ingreso bajo y score B', 'interno'),
    ('E6', 'Perfil ingreso bajo y score C', 'interno'),
    ('E7', 'Validacion de exclusiones (estudio)', 'interno'),
    ('E8', 'Endeudamiento mayor a 75 y menor o igual a 90 por ciento', 'interno'),
    ('E9', 'Sin capacidad para moto solicitada', 'interno')
ON CONFLICT (codigo) DO NOTHING;
-- Usuarios de prueba de la plataforma (auth JWT). Contraseñas bcrypt:
--   admin@pacifico.co / Admin123!    (admin: ve todo)
--   asesor@pacifico.co / Asesor123!  (asesor: SUMOTO SA PALMIRA)
--   aliado@pacifico.co / Aliado123!  (aliado: Inversiones Pacífico)
-- Va al final del archivo: depende de rol, concesionario y
-- aliado_financiero ya sembrados arriba.
-- UUIDs en hex de 32 (sin guiones): Postgres los acepta en columnas
-- uuid y SQLite los guarda igual que el ORM (CHAR(32) value.hex).
INSERT INTO usuario (id_usuario, correo, hash_contrasena, estado, nombre_completo, fecha_verificacion) VALUES
    ('0000000000004000800000000000000a', 'admin@pacifico.co', '$2b$12$5XYg0Klh2zHX6SEkGB9aQ.nx.OFj6HgkNLdAXgErT98sYAPGgfxDO', 'activo', 'Administrador Plataforma', CURRENT_TIMESTAMP),
    ('0000000000004000800000000000001a', 'asesor@pacifico.co', '$2b$12$kgMN4JFNA8mB9ak/aftAueZ2djG5QcixL5cchV5iolgYo9dkt8fQa', 'activo', 'Asesor de Prueba', CURRENT_TIMESTAMP),
    ('0000000000004000800000000000002a', 'aliado@pacifico.co', '$2b$12$TJqL5OAtBDvZCDFacbiepuli3/EmXwD5XZ.B6duwinPLxBTLx2pQa', 'activo', 'Aliado de Prueba', CURRENT_TIMESTAMP)
ON CONFLICT (correo) DO NOTHING;

INSERT INTO usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM usuario u
-- CAST a TEXT: r.nombre es el enum rol_usuario en Postgres y un
-- varchar en SQLite; el CASE produce texto — el cast iguala ambos.
JOIN rol r ON CAST(r.nombre AS TEXT) = CASE u.correo
    WHEN 'admin@pacifico.co' THEN 'admin'
    WHEN 'asesor@pacifico.co' THEN 'asesor'
END
WHERE u.correo IN ('admin@pacifico.co', 'asesor@pacifico.co', 'aliado@pacifico.co')
ON CONFLICT (id_usuario, id_rol) DO NOTHING;

INSERT INTO asesor (id_usuario, nombre, id_concesionario)
SELECT u.id_usuario, u.nombre_completo, c.id_concesionario
FROM usuario u
JOIN concesionario c ON c.nombre = 'SUMOTO SA PALMIRA'
WHERE u.correo = 'asesor@pacifico.co'
ON CONFLICT (id_usuario) DO NOTHING;

INSERT INTO aliado_usuario (id_usuario, id_aliado, rol_interno)
SELECT u.id_usuario, a.id_aliado, 'comercial'
FROM usuario u
JOIN aliado_financiero a ON a.nit = '814005081'
WHERE u.correo = 'aliado@pacifico.co'
ON CONFLICT (id_usuario, id_aliado) DO NOTHING;
