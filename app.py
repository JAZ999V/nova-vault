import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import mercadopago

app = Flask(__name__)
app.secret_key = "nova_vault_secret_key"

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="nova_vault"
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    mensaje = ""
    if request.method == "POST":
        nombre = request.form["nombre"]
        correo = request.form["correo"]
        password = generate_password_hash(request.form["password"])

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO usuarios (nombre, correo, password, rol) VALUES (%s, %s, %s, %s)",
                (nombre, correo, password, "cliente")
            )
            db.commit()
            mensaje = "Usuario registrado correctamente."
        except Exception as e:
            mensaje = "Error: el correo ya puede estar registrado."
        finally:
            cursor.close()
            db.close()

    return render_template("registro.html", mensaje=mensaje)

@app.route("/login", methods=["GET", "POST"])
def login():
    mensaje = ""
    if request.method == "POST":
        correo = request.form["correo"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE correo=%s", (correo,))
        usuario = cursor.fetchone()
        cursor.close()
        db.close()

        if usuario and (check_password_hash(usuario["password"], password) or usuario["password"] == password):
            session["id_usuario"] = usuario["id_usuario"]
            session["nombre"] = usuario["nombre"]
            session["rol"] = usuario["rol"]
            return redirect("/catalogo")
        else:
            mensaje = "Correo o contraseña incorrectos."

    return render_template("login.html", mensaje=mensaje)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/catalogo")
def catalogo():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            s.*,
            (
                SELECT COUNT(*)
                FROM ofertas o
                WHERE o.id_subasta = s.id_subasta
            ) AS total_ofertas
        FROM subastas s
        WHERE s.estado='activa'
        ORDER BY s.fecha_fin ASC
    """)

    subastas = cursor.fetchall()

    cursor.close()
    db.close()

    error = request.args.get("error")
    
    return render_template(
        "catalogo.html",
        subastas=subastas,
        error=error
)



@app.route("/subasta/<int:id_subasta>", methods=["GET", "POST"])
def subasta(id_subasta):

    mensaje = ""

    if request.method == "POST":

        if "id_usuario" not in session:
            mensaje = "Debes iniciar sesión para pujar."

        else:
            db = get_db()
            cursor = db.cursor(dictionary=True)

            cursor.execute(
                "SELECT fecha_fin, precio_actual FROM subastas WHERE id_subasta=%s",
                (id_subasta,)
            )

            datos = cursor.fetchone()

            from datetime import datetime

            if datetime.now() > datos["fecha_fin"]:
                mensaje = "La subasta ya finalizó. No se pueden realizar más ofertas."

            else:
                monto = float(request.form["monto"])

                if monto > float(datos["precio_actual"]):

                    cursor.execute(
                        "INSERT INTO ofertas (id_usuario,id_subasta,monto) VALUES (%s,%s,%s)",
                        (session["id_usuario"], id_subasta, monto)
                    )

                    cursor.execute(
                        "UPDATE subastas SET precio_actual=%s WHERE id_subasta=%s",
                        (monto, id_subasta)
                    )

                    db.commit()
                    mensaje = "Oferta registrada correctamente."

                else:
                    mensaje = "La oferta debe ser mayor a la puja actual."

            cursor.close()
            db.close()

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM subastas WHERE id_subasta=%s",
        (id_subasta,)
    )

    subasta = cursor.fetchone()

    cursor.execute("""
        SELECT o.monto, o.fecha, u.nombre
        FROM ofertas o
        INNER JOIN usuarios u ON o.id_usuario = u.id_usuario
        WHERE o.id_subasta=%s
        ORDER BY o.monto DESC
    """, (id_subasta,))

    ofertas = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "subasta.html",
        subasta=subasta,
        ofertas=ofertas,
        mensaje=mensaje
    )


@app.route("/seguimiento")
def seguimiento():
    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            c.id_carrito,
            c.cantidad,
            s.id_subasta,
            s.titulo,
            s.precio_actual,
            (c.cantidad * s.precio_actual) AS subtotal
        FROM carrito c
        INNER JOIN subastas s
            ON c.id_subasta = s.id_subasta
        WHERE c.id_usuario = %s
    """, (session["id_usuario"],))

    items = cursor.fetchall()

    cursor.close()
    db.close()

    total = sum(float(item["subtotal"]) for item in items)

    return render_template(
    "seguimiento.html",
    items=items,
    total=total
)

@app.route("/ganados")
def ganados():

    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            s.id_subasta,
            s.titulo,
            s.precio_actual
        FROM subastas s
        WHERE s.fecha_fin < NOW()
        AND (
            SELECT o.id_usuario
            FROM ofertas o
            WHERE o.id_subasta=s.id_subasta
            ORDER BY o.monto DESC
            LIMIT 1
        )=%s
    """, (session["id_usuario"],))

    items = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "ganados.html",
        items=items
    )

@app.route("/agregar_carrito/<int:id_subasta>")
def agregar_carrito(id_subasta):

    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM carrito
        WHERE id_usuario=%s AND id_subasta=%s
    """, (session["id_usuario"], id_subasta))

    existe = cursor.fetchone()

    if existe:
        cursor.execute("""
            UPDATE carrito
            SET cantidad = cantidad + 1
            WHERE id_usuario=%s AND id_subasta=%s
        """, (session["id_usuario"], id_subasta))
    else:
        cursor.execute("""
            INSERT INTO carrito (id_usuario, id_subasta, cantidad)
            VALUES (%s, %s, 1)
        """, (session["id_usuario"], id_subasta))

    db.commit()

    cursor.close()
    db.close()

    return redirect("/seguimiento")

@app.route("/quitar_seguimiento/<int:id_carrito>")
def quitar_seguimiento(id_carrito):

    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        DELETE FROM carrito
        WHERE id_carrito=%s
        AND id_usuario=%s
    """, (
        id_carrito,
        session["id_usuario"]
    ))

    db.commit()

    cursor.close()
    db.close()

    return redirect("/seguimiento")

@app.route("/pagos/<int:id_subasta>", methods=["GET", "POST"])
def pagos(id_subasta):
    if "id_usuario" not in session:
        return redirect("/login")

    mensaje = ""

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM subastas WHERE id_subasta=%s",
        (id_subasta,)
    )
    subasta = cursor.fetchone()

    if request.method == "POST":

        metodo_pago = request.form["metodo_pago"]

        cursor.execute("""
            INSERT INTO pagos
            (id_usuario, id_subasta, monto, metodo_pago, estado)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session["id_usuario"],
            id_subasta,
            subasta["precio_actual"],
            metodo_pago,
            "pagado"
        ))

        cursor.execute(
            "UPDATE subastas SET estado='cerrada' WHERE id_subasta=%s",
            (id_subasta,)
        )

        db.commit()

        cursor.close()
        db.close()

        return render_template(
            "comprobante.html",
            subasta=subasta,
            metodo_pago=metodo_pago
        )

    cursor.close()
    db.close()

    return render_template(
        "pagos.html",
        subasta=subasta,
        mensaje=mensaje
    )



@app.route("/admin")
def admin():
    if "id_usuario" not in session:
        return redirect("/login")

    if session.get("rol") != "admin":
        return redirect("/catalogo")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
    usuarios = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM subastas")
    subastas = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM pagos")
    pagos = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT id_usuario, nombre, correo, rol
        FROM usuarios
    """)
    lista_usuarios = cursor.fetchall()

    cursor.execute("""
        SELECT id_subasta, titulo, categoria, precio_actual, estado
        FROM subastas
    """)
    lista_subastas = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin.html",
        usuarios=usuarios,
        subastas=subastas,
        pagos=pagos,
        lista_usuarios=lista_usuarios,
        lista_subastas=lista_subastas
    )

@app.route("/admin_ofertas/<int:id_subasta>")
def admin_ofertas(id_subasta):

    if "id_usuario" not in session:
        return redirect("/login")

    if session.get("rol") != "admin":
        return redirect("/catalogo")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            o.id_oferta,
            o.monto,
            o.fecha,
            u.nombre,
            u.correo
        FROM ofertas o
        INNER JOIN usuarios u
            ON o.id_usuario = u.id_usuario
        WHERE o.id_subasta = %s
        ORDER BY o.monto DESC
    """, (id_subasta,))

    ofertas = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin_ofertas.html",
        ofertas=ofertas,
        id_subasta=id_subasta
    )

@app.route("/eliminar_oferta/<int:id_oferta>/<int:id_subasta>")
def eliminar_oferta(id_oferta, id_subasta):

    if "id_usuario" not in session:
        return redirect("/login")

    if session.get("rol") != "admin":
        return redirect("/catalogo")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Eliminar oferta
    cursor.execute(
        "DELETE FROM ofertas WHERE id_oferta=%s",
        (id_oferta,)
    )

    # Buscar la oferta más alta restante
    cursor.execute("""
        SELECT MAX(monto) AS mayor
        FROM ofertas
        WHERE id_subasta=%s
    """, (id_subasta,))

    mayor = cursor.fetchone()["mayor"]

    # Si ya no quedan ofertas
    if mayor is None:

        cursor.execute("""
            SELECT precio_inicial
            FROM subastas
            WHERE id_subasta=%s
        """, (id_subasta,))

        mayor = cursor.fetchone()["precio_inicial"]

    # Actualizar precio actual
    cursor.execute("""
        UPDATE subastas
        SET precio_actual=%s
        WHERE id_subasta=%s
    """, (mayor, id_subasta))

    db.commit()

    cursor.close()
    db.close()

    return redirect(f"/admin_ofertas/{id_subasta}")

@app.route("/crear_subasta", methods=["GET", "POST"])
def crear_subasta():

    if "id_usuario" not in session:
        return redirect("/login")

    if request.method == "POST":

        titulo = request.form["titulo"]
        descripcion = request.form["descripcion"]
        categoria = request.form["categoria"]
        precio_inicial = request.form["precio_inicial"]
        fecha_fin = request.form["fecha_fin"]
        archivo = request.files["imagen"]
        nombre_imagen = secure_filename(archivo.filename)
        ruta_imagen = os.path.join("static", "img", nombre_imagen)
        archivo.save(ruta_imagen)

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO subastas
            (
                titulo,
                descripcion,
                categoria,
                precio_inicial,
                precio_actual,
                fecha_inicio,
                fecha_fin,
                estado,
                imagen,
                creador_id
            )
            VALUES
            (%s,%s,%s,%s,%s,NOW(),%s,'activa',%s,%s)
        """, (
            titulo,
            descripcion,
            categoria,
            precio_inicial,
            precio_inicial,
            fecha_fin,
            nombre_imagen,
            session["id_usuario"]
        ))

        db.commit()
        cursor.close()
        db.close()

        return redirect("/catalogo")

    return render_template("crear_subasta.html")

@app.route("/eliminar_subasta/<int:id_subasta>")
def eliminar_subasta(id_subasta):

    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Verificar ofertas
    cursor.execute(
        "SELECT COUNT(*) AS total FROM ofertas WHERE id_subasta=%s",
        (id_subasta,)
    )

    total_ofertas = cursor.fetchone()["total"]

    # Si no es admin y ya tiene ofertas
    if session.get("rol") != "admin" and total_ofertas > 0:
        cursor.close()
        db.close()
        return redirect("/catalogo?error=ofertas")
    

    # Eliminar ofertas primero
    cursor.execute(
        "DELETE FROM ofertas WHERE id_subasta=%s",
        (id_subasta,)
    )

    # Eliminar subasta
    cursor.execute(
        "DELETE FROM subastas WHERE id_subasta=%s",
        (id_subasta,)
    )

    db.commit()

    cursor.close()
    db.close()

    return redirect("/catalogo")

@app.route("/mis_subastas")
def mis_subastas():
    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            s.*,
            (
                SELECT COUNT(*)
                FROM ofertas o
                WHERE o.id_subasta = s.id_subasta
            ) AS total_ofertas
        FROM subastas s
        WHERE s.creador_id = %s
        ORDER BY s.fecha_fin ASC
    """, (session["id_usuario"],))

    subastas = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("mis_subastas.html", subastas=subastas)

@app.route("/editar_subasta/<int:id_subasta>", methods=["GET", "POST"])
def editar_subasta(id_subasta):

    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM subastas WHERE id_subasta=%s",
        (id_subasta,)
    )
    subasta = cursor.fetchone()

    if not subasta:
        cursor.close()
        db.close()
        return redirect("/admin")

    # Solo puede editar el admin o el creador
    if session.get("rol") != "admin" and subasta["creador_id"] != session["id_usuario"]:
        cursor.close()
        db.close()
        return redirect("/catalogo")

    if request.method == "POST":
        titulo = request.form["titulo"]
        descripcion = request.form["descripcion"]
        categoria = request.form["categoria"]
        fecha_fin = request.form["fecha_fin"]

        cursor.execute("""
            UPDATE subastas
            SET titulo=%s,
                descripcion=%s,
                categoria=%s,
                fecha_fin=%s
            WHERE id_subasta=%s
        """, (
            titulo,
            descripcion,
            categoria,
            fecha_fin,
            id_subasta
        ))

        db.commit()

        cursor.close()
        db.close()

        if session.get("rol") == "admin":
            return redirect("/admin")
        else:
            return redirect("/mis_subastas")

    cursor.close()
    db.close()

    return render_template("editar_subasta.html", subasta=subasta)

@app.route("/mercadopago/<int:id_subasta>")
def mercadopago_pago(id_subasta):
    if "id_usuario" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM subastas WHERE id_subasta=%s", (id_subasta,))
    subasta = cursor.fetchone()

    cursor.close()
    db.close()

    sdk = mercadopago.SDK("TEST_ACCESS_TOKEN")

    preference_data = {
        "items": [
            {
                "title": subasta["titulo"],
                "quantity": 1,
                "currency_id": "MXN",
                "unit_price": float(subasta["precio_actual"])
            }
        ],
        "back_urls": {
            "success": "http://127.0.0.1:5000/ganados",
            "failure": "http://127.0.0.1:5000/ganados",
            "pending": "http://127.0.0.1:5000/ganados"
        },
        "auto_return": "approved"
    }

    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]

    return redirect(preference["init_point"])


if __name__ == "__main__":
    app.run(debug=True)
