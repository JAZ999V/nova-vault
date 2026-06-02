CREATE DATABASE IF NOT EXISTS nova_vault;
USE nova_vault;

DROP TABLE IF EXISTS pagos;
DROP TABLE IF EXISTS ofertas;
DROP TABLE IF EXISTS subastas;
DROP TABLE IF EXISTS usuarios;

CREATE TABLE usuarios (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  correo VARCHAR(100) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  rol ENUM('admin', 'cliente') DEFAULT 'cliente',
  fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subastas (
  id_subasta INT AUTO_INCREMENT PRIMARY KEY,
  titulo VARCHAR(120) NOT NULL,
  descripcion TEXT,
  categoria VARCHAR(80),
  precio_inicial DECIMAL(10,2) NOT NULL,
  precio_actual DECIMAL(10,2) NOT NULL,
  fecha_inicio DATETIME,
  fecha_fin DATETIME,
  estado ENUM('activa', 'cerrada', 'cancelada') DEFAULT 'activa'
);

CREATE TABLE ofertas (
  id_oferta INT AUTO_INCREMENT PRIMARY KEY,
  id_usuario INT,
  id_subasta INT,
  monto DECIMAL(10,2) NOT NULL,
  fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
  FOREIGN KEY (id_subasta) REFERENCES subastas(id_subasta)
);

CREATE TABLE pagos (
  id_pago INT AUTO_INCREMENT PRIMARY KEY,
  id_usuario INT,
  id_subasta INT,
  monto DECIMAL(10,2) NOT NULL,
  metodo_pago VARCHAR(50),
  estado ENUM('pendiente', 'pagado', 'rechazado') DEFAULT 'pendiente',
  fecha_pago DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
  FOREIGN KEY (id_subasta) REFERENCES subastas(id_subasta)
);

INSERT INTO usuarios (nombre, correo, password, rol) VALUES
('Administrador NOVA', 'admin@novavault.com', '123456', 'admin'),
('Usuario Demo', 'usuario@novavault.com', '123456', 'cliente');

INSERT INTO subastas (titulo, descripcion, categoria, precio_inicial, precio_actual, fecha_inicio, fecha_fin, estado) VALUES
('Laptop Gamer Nova X', 'Laptop de alto rendimiento para gaming y diseño.', 'Tecnología', 9000, 12000, NOW(), DATE_ADD(NOW(), INTERVAL 2 HOUR), 'activa'),
('Smartwatch Vault Pro', 'Reloj inteligente con monitoreo deportivo.', 'Accesorios', 1000, 1800, NOW(), DATE_ADD(NOW(), INTERVAL 45 MINUTE), 'activa'),
('Consola NextPlay 5', 'Consola de videojuegos de última generación.', 'Videojuegos', 7000, 8500, NOW(), DATE_ADD(NOW(), INTERVAL 1 HOUR), 'activa');
