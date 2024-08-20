from calendar import monthrange
from datetime import datetime
import fitz  # PyMuPDF
import io
import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import config

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Custom number format filter for Jinja2
def number_format(value, decimal_places=2):
    return f"{float(value):,.{decimal_places}f}"

app.jinja_env.filters['number_format'] = number_format

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
            session['admin'] = True
            if 'employees' not in session:
                session['employees'] = []  # Initialize the employee list in session
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid credentials, try again."
    return render_template('login.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        employees = session.get('employees', [])

        if 'add_employee' in request.form:
            name = request.form['name']
            monthly_salary = request.form['monthly_salary']
            phone_number = request.form['phone_number']
            id_number = request.form['id_number']
            start_date = request.form['start_date']
            address = request.form['address']

            try:
                parsed_start_date = datetime.strptime(start_date, '%d/%m/%Y')
            except ValueError:
                return "Invalid start date format. Please use DD/MM/YYYY."

            formatted_start_date = parsed_start_date.strftime('%d/%m/%Y')
            employee_id = len(employees) + 1

            employees.append({
                'id': employee_id,
                'name': name,
                'monthly_salary': monthly_salary,
                'phone_number': phone_number,
                'id_number': id_number,
                'start_date': formatted_start_date,
                'address': address,
                'holidays_taken': 0  # Initialize holidays taken
            })

        elif 'update_employee' in request.form:
            employee_id = int(request.form['employee_id'])
            new_salary = request.form['new_salary']
            new_phone_number = request.form['new_phone_number']
            new_address = request.form['new_address']

            for employee in employees:
                if employee['id'] == employee_id:
                    employee['monthly_salary'] = new_salary
                    employee['phone_number'] = new_phone_number
                    employee['address'] = new_address
                    break

        elif 'delete_employee' in request.form:
            employee_id = int(request.form['employee_id'])
            employees = [e for e in employees if e['id'] != employee_id]

        session['employees'] = employees
        return redirect(url_for('employee_list'))

    return render_template('admin_dashboard.html')

@app.route('/employee_list')
def employee_list():
    if 'admin' not in session:
        return redirect(url_for('login'))

    employees = session.get('employees', [])

    # Format the salary before passing it to the template
    for employee in employees:
        employee['formatted_salary'] = f"{float(employee['monthly_salary']):,.2f}"

    return render_template('employee_list.html', employees=employees)

@app.route('/employee_history/<int:employee_id>')
def employee_history(employee_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    employees = session.get('employees', [])
    employee = next((e for e in employees if e['id'] == employee_id), None)

    if not employee:
        return "Employee not found."

    # Directory where PDFs are stored
    pdf_directory = os.path.join('static', 'pdfs')

    # Get the current sanitized name format
    sanitized_name = employee['name'].replace(" ", "_")
    current_date = datetime.now().strftime('%B_%Y')

    # Find all PDF files for this employee
    pdf_files = []
    if os.path.exists(pdf_directory):
        pdf_files = [f for f in os.listdir(pdf_directory) if f.startswith(f"{sanitized_name}_") and f.endswith(".pdf")]

    # Ensure that the formatted salary is prepared
    employee['formatted_salary'] = f"{float(employee['monthly_salary']):,.2f}"

    return render_template('employee_history.html', employee=employee, pdf_files=pdf_files)


@app.route('/employee_details/<int:employee_id>', methods=['GET', 'POST'])
def employee_details(employee_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    employees = session.get('employees', [])
    employee = next((e for e in employees if e['id'] == employee_id), None)

    if not employee:
        return "Employee not found."

    now = datetime.now()
    current_month = now.strftime('%B %Y')
    num_days = monthrange(now.year, now.month)[1]

    salary_before = float(employee['monthly_salary'])
    salary_per_day = round(salary_before / num_days, 2)
    salary_per_hour = round(salary_per_day / 9, 2)

    days_absent = employee.get('days_absent', 0)
    extra_days = employee.get('extra_days', 0)
    hours_absent = employee.get('hours_absent', 0)
    extra_hours = employee.get('extra_hours', 0)
    advanced_payment = employee.get('advanced_payment', 0.0)
    holidays_taken = employee.get('holidays_taken', 0)  # New field for holidays taken
    holidays_value = f"{holidays_taken}/14"  # Display as taken/total
    salary_after = employee.get('salary_after', salary_before)

    if request.method == 'POST':
        days_absent = int(request.form['days_absent'])
        hours_absent = int(request.form['hours_absent'])
        extra_days = int(request.form['extra_days'])
        extra_hours = int(request.form['extra_hours'])
        advanced_payment = float(request.form['advanced_payment'])
        holidays_taken = int(request.form['holidays_taken'])  # Update holidays taken

        salary_after = (
            salary_before - advanced_payment
            - days_absent * salary_per_day
            - hours_absent * salary_per_hour
            + extra_days * salary_per_day
            + extra_hours * salary_per_hour
        )
        salary_after = round(salary_after, 2)

        employee.update({
            'days_absent': days_absent,
            'hours_absent': hours_absent,
            'extra_days': extra_days,
            'extra_hours': extra_hours,
            'advanced_payment': advanced_payment,
            'holidays_taken': holidays_taken,  # Save the updated holidays taken
            'salary_after': salary_after,
        })

        session['employees'] = employees

        return redirect(url_for('employee_details', employee_id=employee_id))

    return render_template('employee_details.html',
                           employee=employee,
                           current_month=current_month,
                           num_days=num_days,
                           salary_before=round(salary_before, 2),
                           salary_per_day=salary_per_day,
                           salary_per_hour=salary_per_hour,
                           days_absent=days_absent,
                           hours_absent=hours_absent,
                           extra_days=extra_days,
                           extra_hours=extra_hours,
                           advanced_payment=round(advanced_payment, 2),
                           holidays_value=holidays_value,  # Pass holidays value to the template
                           salary_after=salary_after)

def calculate_equivalent_number(employee, extra_hours):
    salary_before = float(employee['monthly_salary'])
    num_days = monthrange(datetime.now().year, datetime.now().month)[1]
    salary_per_day = salary_before / num_days
    salary_per_hour = salary_per_day / 9
    return extra_hours * salary_per_hour

@app.route('/generate_pdf/<int:employee_id>', methods=['GET'])
def generate_pdf(employee_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    employees = session.get('employees', [])
    employee = next((e for e in employees if e['id'] == employee_id), None)

    if not employee:
        return "Employee not found."

    try:
        extra_hours = employee.get('extra_hours', 0)
        extra_days = employee.get('extra_days', 0)
        days_absent = employee.get('days_absent', 0)
        equivalent_hours = calculate_equivalent_number(employee, extra_hours)
        equivalent_days = extra_days * (float(employee['monthly_salary']) / monthrange(datetime.now().year, datetime.now().month)[1])
        equivalent_days_absent = days_absent * (float(employee['monthly_salary']) / monthrange(datetime.now().year, datetime.now().month)[1])

        # Update the template path with your actual PDF template path
        template_path = os.path.join('static', 'baldna salaries.pdf')
        if not os.path.exists(template_path):
            return "Template file not found."

        doc = fitz.open(template_path)
        page = doc[0]

        def insert_text(position, text, font_size=12, font_color=(0, 0, 0)):
            page.insert_text(position, text, fontsize=font_size, color=font_color)

        font_size = 12
        font_color = (0, 0, 0)

        # Insert various details into the PDF
        insert_text((110, 208), datetime.now().strftime('%d/%m/%Y'), font_size, font_color)
        insert_text((370, 248), employee['name'], font_size, font_color)
        insert_text((380, 276), employee['id_number'], font_size, font_color)
        insert_text((390, 304), employee['address'], font_size, font_color)
        insert_text((235, 390), str(employee['monthly_salary']), font_size, font_color)
        insert_text((255, 417), str(employee.get('extra_hours', 0)), font_size, font_color)
        insert_text((158, 417), f"{equivalent_hours:.2f}", font_size, font_color)
        insert_text((265, 445), str(employee.get('extra_days', 0)), font_size, font_color)
        insert_text((159, 445), f"{equivalent_days:.2f}", font_size, font_color)
        insert_text((280, 472), str(employee.get('days_absent', 0)), font_size, font_color)
        insert_text((175, 472), f"{equivalent_days_absent:.2f}", font_size, font_color)  
        insert_text((312, 500), str(employee.get('advanced_payment', 0)), font_size, font_color)
        insert_text((260, 555), str(employee.get('salary_after', 0)), font_size, font_color)

        # Save the PDF to a byte stream
        pdf_bytes = io.BytesIO()
        doc.save(pdf_bytes)
        pdf_bytes.seek(0)
        doc.close()

        # Serve the PDF directly in the browser
        return send_file(
            pdf_bytes,
            as_attachment=False,
            download_name=f"{employee['name']}_details.pdf",
            mimetype='application/pdf')

    except Exception as e:
        print(f"Error generating PDF: {e}")
        return "An error occurred while generating the PDF."

@app.route('/save_pdf/<int:employee_id>', methods=['GET'])
def save_pdf(employee_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    employees = session.get('employees', [])
    employee = next((e for e in employees if e['id'] == employee_id), None)

    if not employee:
        return "Employee not found."

    try:
        # Generate PDF content
        extra_hours = employee.get('extra_hours', 0)
        extra_days = employee.get('extra_days', 0)
        days_absent = employee.get('days_absent', 0)
        equivalent_hours = calculate_equivalent_number(employee, extra_hours)
        equivalent_days = extra_days * (float(employee['monthly_salary']) / monthrange(datetime.now().year, datetime.now().month)[1])
        equivalent_days_absent = days_absent * (float(employee['monthly_salary']) / monthrange(datetime.now().year, datetime.now().month)[1])

        # Update the template path with your actual PDF template path
        template_path = os.path.join('static', 'baldna salaries.pdf')
        if not os.path.exists(template_path):
            return "Template file not found."

        doc = fitz.open(template_path)
        page = doc[0]

        def insert_text(position, text, font_size=12, font_color=(0, 0, 0)):
            page.insert_text(position, text, fontsize=font_size, color=font_color)

        font_size = 12
        font_color = (0, 0, 0)

        # Insert various details into the PDF
        insert_text((110, 208), datetime.now().strftime('%d/%m/%Y'), font_size, font_color)
        insert_text((370, 248), employee['name'], font_size, font_color)
        insert_text((380, 276), employee['id_number'], font_size, font_color)
        insert_text((390, 304), employee['address'], font_size, font_color)
        insert_text((235, 390), str(employee['monthly_salary']), font_size, font_color)
        insert_text((255, 417), str(employee.get('extra_hours', 0)), font_size, font_color)
        insert_text((158, 417), f"{equivalent_hours:.2f}", font_size, font_color)
        insert_text((265, 445), str(employee.get('extra_days', 0)), font_size, font_color)
        insert_text((159, 445), f"{equivalent_days:.2f}", font_size, font_color)
        insert_text((280, 472), str(employee.get('days_absent', 0)), font_size, font_color)
        insert_text((175, 472), f"{equivalent_days_absent:.2f}", font_size, font_color)  
        insert_text((312, 500), str(employee.get('advanced_payment', 0)), font_size, font_color)
        insert_text((260, 555), str(employee.get('salary_after', 0)), font_size, font_color)

        # Save the PDF to a specific directory
        pdf_directory = os.path.join('static', 'pdfs')
        if not os.path.exists(pdf_directory):
            os.makedirs(pdf_directory)

        # Format the filename to include employee name and current month/year
        current_date = datetime.now().strftime('%B_%Y')  # Format as 'Month_Year'
        sanitized_name = employee['name'].replace(" ", "_")  # Replace spaces with underscores
        pdf_filename = f"{sanitized_name}_{current_date}.pdf"
        pdf_filepath = os.path.join(pdf_directory, pdf_filename)
        
        doc.save(pdf_filepath)
        doc.close()

        return f"PDF saved successfully as {pdf_filename}."

    except Exception as e:
        print(f"Error saving PDF: {e}")
        return "An error occurred while saving the PDF."


if __name__ == '__main__':
    app.run(debug=True)
