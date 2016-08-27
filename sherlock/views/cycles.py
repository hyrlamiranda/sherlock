"""Sherlock Cycles Controllers and Routes."""
from flask import Blueprint, request, url_for, redirect, g, flash, jsonify
from flask import render_template
from flask_login import login_required
from flask_babel import gettext


from sherlock import db
from sherlock.data.model import Scenario, Project, Case, Cycle, CycleHistory
from sherlock.data.model import State
from sherlock.helpers.object_loader import load_cycle_history, count_cycle_stats
from sherlock.helpers.object_loader import load_cases_names_for_cycle


cycle = Blueprint('cycle', __name__)


@cycle.url_value_preprocessor
@login_required
def get_cycles(endpoint, values):
    """Blueprint Object Query."""
    project = Project.query.filter_by(id=values.pop('project_id')).one()
    g.project = project

    if 'cycle_id' in values:
        g.project_cycle = Cycle.query.filter_by(
            id=values.pop('cycle_id')).first_or_404()

        load_cycle_history(g.project_cycle, CycleHistory)

        g.cycle_history_formated = load_cases_names_for_cycle(Scenario, Case,
                                                              CycleHistory,
                                                              g.project_cycle)

    else:
        g.current_cycle = Cycle.query.order_by(
            '-id').filter_by(project_id=g.project.id).first()

    if g.current_cycle:
        if g.current_cycle.state_code == "CLOSED":
            g.current_cycle_status_open = False
        else:
            g.current_cycle_status_open = True
    else:
        g.current_cycle_status_open = False


@cycle.route('/create', methods=['POST'])
@login_required
def create():
    if request.method == 'POST':

        if g.current_cycle_status_open:
            flash(gettext('Close the current cycle first'), 'danger')
            return redirect(url_for('projects.show', project_id=g.project.id))

        cases = Case.query.join(
            Scenario, Case.scenario_id == Scenario.id).filter(
                Scenario.project_id == g.project.id).filter(
                    Case.state_code == "ACTIVE")

        if cases.count() == 0:
            flash(gettext('You dont have any Test Cases or Scenarios '
                          'to create a cycle'), 'danger')
            return redirect(url_for('projects.show', project_id=g.project.id))

        if g.current_cycle:
            cycle_number = int(g.current_cycle.number) + 1
        else:
            cycle_number = 1

        new_cycle = Cycle(
            number=cycle_number, project_id=g.project.id)
        db.session.add(new_cycle)
        db.session.commit()

        for case in cases:
            item = CycleHistory(cycle_id=new_cycle.id, case_id=case.id,
                                scenario_id=case.scenario_id)
            db.session.add(item)
            db.session.commit()
        return redirect(url_for('cycles.show', project_id=g.project.id,
                        cycle_id=new_cycle.id))
    return redirect(url_for('projects.show', project_id=g.project.id))


@cycle.route('/show/<int:cycle_id>', methods=['GET'])
@login_required
def show():
    return render_template("cycle/show.html")


@cycle.route('/get_states/<int:cycle_id>', methods=['GET'])
@login_required
def get_cycle_cases_states_count():
    cycle_history = CycleHistory.query.filter_by(
        cycle_id=g.project_cycle.id)
    count = count_cycle_stats(cycle_history)
    return jsonify({"total_error": count['total_error'],
                    "total_passed": count['total_passed'],
                    "total_blocked": count['total_blocked'],
                    "total_not_executed": count['total_not_executed']})


@cycle.route('/edit/<int:cycle_id>', methods=['POST'])
@login_required
def change_case_status_for_cycle_history():
    if request.method == 'POST':
        state_code = request.get_json().get('state_code')
        case_id = request.get_json().get('case_id')
        State.query.filter_by(code=state_code).first_or_404()
        edited_cycle_case = CycleHistory.query.filter_by(
            cycle_id=g.project_cycle.id).filter_by(case_id=case_id).first()
        edited_cycle_case.state_code = state_code
        db.session.add(edited_cycle_case)
        db.session.commit()

        return jsonify({"status": "ok",
                        "case_id": case_id,
                        "state_code": state_code})
