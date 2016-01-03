from flask import Flask, render_template, request, redirect, url_for, abort
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, login_required, login_user, logout_user, current_user
from flask.ext.migrate import Migrate, MigrateCommand
from flask.ext.script import Manager
from flask.ext.bcrypt import Bcrypt
import datetime
import cloudinary.uploader
import os
import stripe

stripe_keys = {
  'secret_key': os.environ.get('SECRET_KEY', 'sk_test_VOef9rynf2MHrpRKOvAJ7Amc'),
  'publishable_key': os.environ.get('PUBLISHABLE_KEY', 'pk_test_aDUTDWThg2IXxTVquMV2cxdo')
}

stripe.api_key = stripe_keys['secret_key']

app = Flask(__name__)
app.config.from_object('launchpad.default_settings')
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)
login_manager = LoginManager()
login_manager.init_app(app)
bcrypt = Bcrypt()


from launchpad.models import *
from .forms import LoginForm

@login_manager.user_loader
def user_loader(user_id):
    """Given *user_id*, return the associated User object.
    :param unicode user_id: user_id (email) user to retrieve
    """
    return User.query.get(user_id)

@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'GET':
     return render_template('register.html')
  elif request.method == 'POST':

    password = request.form.get("password")

    new_user = User(
      id = request.form.get("email").lower(),
      password = bcrypt.generate_password_hash(password),
      authenticated = True,
      first_name = request.form.get("first_name"),
      last_name = request.form.get("last_name")
    )

    db.session.add(new_user)
    db.session.commit()
    login_user(new_user, remember=True)

    return redirect('/')
  else:
    abort(405)

@app.route("/login", methods=["GET", "POST"])
def login():
    """For GET requests, display the login form. For POSTS, login the current user
    by processing the form."""
    print db
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.get(form.email.data.lower())
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                user.authenticated = True
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                return redirect('/')
    return render_template("login.html", form=form)

@app.route("/logout", methods=["GET"])
@login_required
def logout():
    """Logout the current user."""
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    return redirect(url_for('hello'))

@app.route("/my_projects")
@login_required
def my_projects():
  projects = db.session.query(Project).filter_by(user_id=current_user.id)
  return render_template("my_projects.html", projects=projects)

@app.route("/")
def hello():
  projects = db.session.query(Project).order_by(Project.time_created.desc()).limit(15)
  return render_template("index.html", projects=projects)

@app.route("/projects/create/", methods=['GET', 'POST'])
@login_required
def create():
  if request.method == "GET":
    return render_template("create.html")
  if request.method == "POST":
    # Handle the form submission

    now = datetime.datetime.now()
    time_end = request.form.get("funding_end_date")
    time_end = datetime.datetime.strptime(time_end, "%Y-%m-%d")

    # Upload cover photo

    cover_photo = request.files['cover_photo']
    uploaded_image = cloudinary.uploader.upload(
      cover_photo,
      crop = 'limit',
      width = '680',
      height = 550
    )
    image_filename = uploaded_image["public_id"]

    new_project = Project(
      user_id = current_user.id, # Guest Creator
      name = request.form.get("project_name"),
      short_description = request.form.get("short_description"),
      long_description = request.form.get("long_description"),
      image_filename = image_filename,
      goal_amount = request.form.get("funding_goal"),
      time_start = now,
      time_end = time_end,
      time_created = now
    )

    db.session.add(new_project)
    db.session.commit()

    return redirect(url_for('project_detail', project_id = new_project.id))

@app.route("/projects/<int:project_id>/")
def project_detail(project_id):
  project = db.session.query(Project).get(project_id)
  if project is None:
    abort(404)

  return render_template("project_detail.html", project=project)

@app.route("/projects/<int:project_id>/edit", methods=['GET', 'POST'])
@login_required
def edit(project_id):
  project = db.session.query(Project).get(project_id)

  if project.user_id != current_user.id:
    return redirect(url_for('project_detail', project_id = project_id))

  if project is None:
    abort(404)

  if request.method == "GET":
    return render_template("edit.html", project=project)

  if request.method == "POST":
    project.short_description = request.form.get("short_description")
    project.long_description = request.form.get("long_description")
    cover_photo = request.files['cover_photo']

    if cover_photo:
      uploaded_image = cloudinary.uploader.upload(
        cover_photo,
        crop = 'limit',
        width = '680',
        height = 550
      )
      image_filename = uploaded_image["public_id"]
      project.image_filename = image_filename

    db.session.commit()
    return redirect(url_for('project_detail', project_id = project.id))

@app.route("/projects/<int:project_id>/delete", methods=['POST'])
@login_required
def delete_project(project_id):
  project = db.session.query(Project).get(project_id)

  if project.user_id == current_user.id:
    db.session.delete(project)
    db.session.commit()

  return redirect(url_for('my_projects'))

@app.route("/projects/<int:project_id>/pledge/")
@login_required
def pledge(project_id):
  project = db.session.query(Project).get(project_id)
  if project is None:
    abort(404)
  
  if request.method == "GET":
    return render_template("pledge.html", project=project)

@app.route("/projects/<int:project_id>/checkout/", methods=['POST'])
@login_required
def checkout(project_id):
  print 'test1---------------------'
  project = db.session.query(Project).get(project_id)
  
  if project is None:
    abort(404)
  
  amount = request.form.get("amount")  
  return render_template('checkout.html', project_id=project.id, amount=amount, key=stripe_keys['publishable_key'])


@app.route("/projects/<int:project_id>/charge/", methods=['POST'])
@login_required
def charge(project_id):
  project = db.session.query(Project).get(project_id)

  if request.method == "POST":
    # Handle the form submission
    customer = stripe.Customer.create(
      email = current_user.id,
      card = request.form['stripeToken']
    )
    print 'test2---------------------'

    amount = request.form.get("amount")

    charge = stripe.Charge.create(
      customer = customer.id,
      amount = amount + "00",
      currency = 'usd',
      description = 'Project Pledge'
    )

    print 'test3---------------------'
    new_pledge = Pledge(
      user_id = current_user.id,
      project_id = project.id,
      amount = amount,
      time_created = datetime.datetime.now()
    )

    db.session.add(new_pledge)
    db.session.commit()

    return render_template('charge.html', project=project, amount=amount)



@app.route('/search/')
def search():
  query = request.args.get("q") or ""
  projects = db.session.query(Project).filter(
    Project.name.ilike('%'+query+'%') |
    Project.short_description.ilike('%'+query+'%') |
    Project.long_description.ilike('%'+query+'%')
  ).all()

  project_count = len(projects)

  return render_template('search.html',
    query_text=query,
    projects=projects,
    project_count=project_count
  )
