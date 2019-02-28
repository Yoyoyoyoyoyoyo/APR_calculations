#### Reg Z APR stuff ####
# Formulas come from: https://www.fdic.gov/regulations/laws/rules/6500-3550.html

# loan_amt: initial amount of A
# payment_amt: periodic payment P
# num_of_pay: total number of payment P
# ppy: number of payment periods per year
# apr_guess: guess to start estimating from. Default = .05, or 5%
# odd_days: odd days, meaning the fraction of a pay period for the first
    # installment. If the pay period is monthly & the first installment is
    # due after 45 days, the odd_days are 15/30.
# full: full pay periods before the first payment. Usually 1
# advance: date the finance contract is supposed to be funded
# first_payment_due: first due date on the finance contract


from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
from operator import itemgetter

TWOPLACES = Decimal(10) ** -2



def regulation_Z_APR_calculation(loan_amt_dict, loan_payment, num_of_pay,
	ppy, first_payment_due, apr_guess=5): # apr_guess: 5 means 5%
	"""Returns the calculated APR using Regulation Z/Truth In Lending
		Appendix J's calculation method"""
	loan_payment = float(loan_payment)
	result = float(apr_guess)
	tempguess = float(apr_guess) + .1

	if len(loan_amt_dict) > 1:
		multiple_policies = True
		loan_amt_dict = sum_advances_per_date(loan_amt_dict)
		block_excessively_long_loops(loan_amt_dict, first_payment_due,
			multiple_policies=multiple_policies)
	else:
		multiple_policies = False
		block_excessively_long_loops(loan_amt_dict[0]['date'],
			first_payment_due, multiple_policies=multiple_policies)

	new_loan_amt, full, odd_days, advance_full, advance_odd = \
		make_variables_for_multi_policies(loan_amt_dict, first_payment_due,
		ppy)

	result = loop_calculating_apr(result, tempguess, ppy, num_of_pay,
		loan_payment, full, odd_days, advance_full, advance_odd,
		new_loan_amt, multiple_policies, loan_amt_dict)

	if result < 0:
		# If apr_guess starts out several times higher than the actual APR,
		# then the 2nd guess can become negative, and instead of converging
		# at the correct APR, the APR guesses will become larger and larger
		# negative numbers, eventually returning an incorrect & negative APR.
		result = float(apr_guess) / 100
		tempguess = (float(apr_guess) / 100) + .1
		result = loop_calculating_apr(result, tempguess, ppy, num_of_pay,
			loan_payment, full, odd_days, advance_full, advance_odd,
			new_loan_amt, multiple_policies, loan_amt_dict)

	return result

## Helper functions
def make_variables_for_multi_policies(loan_amt_dict, first_payment_due, ppy):
	"""Make the extra variables needed for loans with multiple policies"""
	new_loan_amt = sum_advances_per_date(loan_amt_dict)
		
	# The 'advance' uses the earliest funding date, which is the first item
	# in the list from new_loan_amt.
	full, odd_days = count_full_and_odd_days(new_loan_amt[0]['date'], 
		first_payment_due, ppy)
	
	# Get the full, odd days for other advances
	advance_full = []
	advance_odd = []
	if len(new_loan_amt) > 1:  ## If using this function, should always be >1
		for item in new_loan_amt[1:]:
			# The first item is the original funding, not needed here
			new_full, new_odd = count_full_and_odd_days(new_loan_amt[0]['date'],
				item['date'], ppy)
			# Measuring days from the first advance until the nth advance
			advance_full += [new_full]
			advance_odd += [new_odd]		

	return new_loan_amt, full, odd_days, advance_full, advance_odd

def count_full_and_odd_days(advance, first_payment_due, ppy):
	"""Takes two datetime.date objects plus the ppy and returns the remainder
	of a pay period	for the first installment of an irregular first payment 
	period (odd_days) and the number of full pay periods before the first 
	installment (full)."""
 
	if isinstance(advance, datetime.date) and isinstance(first_payment_due, 
		datetime.date):
		advance_to_first = -relativedelta(advance, first_payment_due)
			# returns a relativedelta object. 
			
			## Appendix J requires calculating odd_days by counting BACKWARDS
			## from the later date, first subtracting full unit-periods, then
			## taking the remainder as odd_days. relativedelta lets you
			## calculate this easily.

			# advance_date = datetime.date(2015, 2, 27)
			# first_pay_date = datetime.date(2015, 4, 1)
			# incorrect = relativedelta(first_pay_date, advance_date)
			# correct = -relativedelta(advance_date, first_pay_date)
			# print("See the difference between ", correct, " and ", incorrect, "?")

		if ppy == 12:
			# If the payment schedule is monthly
			full = advance_to_first.months + (advance_to_first.years * 12)
			odd_days = advance_to_first.days / 30
			if odd_days == 1:
				odd_days = 0
				full += 1
				# Appendix J (b)(5)(ii) requires the use of 30 in the 
				# denominator even if a month has 31 days, so Jan 1 to Jan 31
				# counts as a full month without any odd days.
			return full, odd_days

		elif ppy == 4:
			# If the payment schedule is quarterly
			full = (advance_to_first.months // 3) + (advance_to_first.years * 4)
			odd_days = ((advance_to_first.months % 3) * 30 + advance_to_first. \
				days) / 90
			if odd_days == 1:
				odd_days = 0
				full += 1
				# Same as above. Sometimes odd_days would be 90/91, but not under
				# Reg Z.
			return full, odd_days
			
		elif ppy == 2:
			# Semiannual payments
			full = (advance_to_first.months // 6) + (advance_to_first.years * 2)
			odd_days = ((advance_to_first.months % 6) * 30 + advance_to_first. \
				days) / 180
			if odd_days == 1:
				odd_days = 0
				full += 1
			return full, odd_days
		
		elif ppy == 24:
			# Semimonthly payments
			full = (advance_to_first.months * 2) + (advance_to_first.years * \
				24)	+ (advance_to_first.days // 15)
			odd_days = ((advance_to_first.days % 15) / 15)
			return full, odd_days

		# Don't worry about test coverage for these.
		# I won't need them for a long time.
		elif ppy == 52:
			# If the payment schedule is weekly, then things get real
			convert_to_days = first_payment_due - advance
				# Making a timedelta object
			if advance_to_first.years == 0:
				full, odd_days = divmod(convert_to_days, datetime.timedelta(
					days=7))
					# Divide, save the remainder
				odd_days = int(odd_days / datetime.timedelta(days=1)) / 7
					# Convert odd_days from a timedelta object to an int
				return full, odd_days
			elif advance_to_first.years != 0 and advance_to_first.months == 0 \
				and advance_to_first.days == 0:  # pragma: no cover
				# An exact year is an edge case. By convention, we consider 
				# this 52 weeks, not 52 weeks & 1 day (2 if a leap year)
				full = 52 * advance_to_first.years
				odd_days = 0
				return full, odd_days                
			else:  # pragma: no cover
				# For >1 year, there need to be exactly 52 weeks per year, 
				# meaning 364 day years. The 365th day is a freebie.
				year_remainder = convert_to_days - datetime.timedelta(days=(
					365 * advance_to_first.years))
				full, odd_days = divmod(year_remainder, datetime.timedelta(
					days=7))
				full += 52 * advance_to_first.years
					# Sum weeks from this year, weeks from past years
				odd_days = int(odd_days / datetime.timedelta(days=1)) / 7
					# Convert odd_days from a timedelta object to an int
				return full, odd_days

		else:
			raise ValueError("The PPY of " + str(ppy) + " isn't an accepted option")

	else:
		raise ValueError("'advance' and 'first_payment_due' should both be datetime.date objects")

def sum_advances_per_date(loan_amt):
	"""Takes a list of dictionaries, sums them by date, and returns a
		list of dictionaries with one entry per funding date and
		sorted chronologically with the earliest funding dates first"""
	# If starting with:
		# [{'loan_amt': 1000, 'date': datetime.date(2015, 6, 1)},
		#	{'loan_amt': 2000, 'date': datetime.date(2015, 6, 15)},
		# 	{'loan_amt': 1500, 'date': datetime.date(2015, 6, 1)}]
	# Should end with:
		# [{'loan_amt': 2500, 'date':datetime.date(2015, 6, 1)},
		#	{'loan_amt': 2000, 'date':datetime.date(2015, 6, 15)}]
		
	# First, sort the dictionaries in loan_amt (the input) by date
	loan_amt.sort(key=itemgetter('date'))
	
	dict_of_dates = {}
	new_list_of_dicts = []
	previously_used_dates = {}

	# Go through each item in loan_amt. If the date has been seen before,
	# add the loan_amt to the loan_amt from the date. If not, make a new 
	# dictionary for new_list_of_dicts and add the date to 
	# previously_used_dates.

	for item in loan_amt:
		if item['date'] in previously_used_dates:
		# If the date has been used before & exists in new_list_of_dicts:
			new_list_of_dicts[-1]['loan_amt'] += item['loan_amt']
			# Because the input (loan_amt) is sorted, duplicate dates are
			# guaranteed to be the last items in the list
		else:
			# Construct and enter the new dictionary item if the date is unique
			new_dict = {'date': item['date'], 'loan_amt': item['loan_amt']}
			new_list_of_dicts.append(new_dict)
			previously_used_dates[item['date']] = 0
			# 0 isn't significant. I'm just putting the date in the dictionary

	return new_list_of_dicts

def general_equation(num_of_pay, payment_amt, full, odd_days, rate,
	advance_full, advance_odd, new_loan_amt):
	# The first item in new_loan_amt is the original advance, which shouldn't 
	# be in this calculation.
	other_advances = sum([new_loan_amt[x+1]['loan_amt'] / ((1.0 + advance_odd[
			x] * rate) * ((1 + rate) ** (advance_full[x]))) for x in range(
			len(advance_full))])

	retval = sum([payment_amt / ((1.0 + odd_days * rate) * ((1.0 + rate) ** (
			x + full))) for x in range(num_of_pay)])

	return retval - other_advances

def block_excessively_long_loops(pol_eff_date, first_payment_due, multiple_policies=False):
	# APR calculations get nasty when first due dates are way before policies
	# are funded. Limit the possibility of this calculation turning into a
	# nearly-infinite loop by returning an error instead.
	if multiple_policies:
		earliest_effective_date = min([pol['date'] for pol in pol_eff_date])
	else:
		earliest_effective_date = pol_eff_date

	if isinstance(earliest_effective_date, datetime.datetime):
		first_eff_date = datetime.date(earliest_effective_date.year,
						earliest_effective_date.month,
						earliest_effective_date.day)
	else:
		first_eff_date = earliest_effective_date

	if isinstance(first_payment_due, datetime.datetime):
		first_due_date = datetime.date(first_payment_due.year,
						first_payment_due.month,
						first_payment_due.day)
	else:
		first_due_date = first_payment_due

	if (first_eff_date - first_due_date).days > 60:
		raise ValueError("The first due date is too early compared to the earliest effective date")

def loop_calculating_apr(result, tempguess, ppy, num_of_pay, loan_payment,
	full, odd_days, advance_full, advance_odd, new_loan_amt,
	multiple_policies, loan_amt_dict):

	# Iterate through the math until you get an answer that's close enough
	while abs(result - tempguess) > .00001:
		result = tempguess
		# Meaning result starts 0.1% higher than apr_guess
		rate = tempguess / (100 * ppy)
		rate2 = (tempguess + 0.1) / (100 * ppy)
		if multiple_policies:
			A1 = general_equation(num_of_pay, loan_payment, full, odd_days,
				rate, advance_full, advance_odd, new_loan_amt)
			A2 = general_equation(num_of_pay, loan_payment, full, odd_days,
				rate2, advance_full, advance_odd, new_loan_amt)
		else: 
			# Doesn't use advance_full, advance_odd b/c they only apply to
			# policies effective after the earliest policy effective date
			A1 = sum([float(loan_payment) / ((1.0 + odd_days * rate) * ((
				1 + rate) ** (x + full))) for x in range(num_of_pay)])
			A2 = sum([float(loan_payment) / ((1.0 + odd_days * rate2) * ((
				1 + rate2) ** (x + full))) for x in range(num_of_pay)])
		try:
			tempguess = tempguess + 0.1 * (float(loan_amt_dict[0]['loan_amt']) - float(A1)) \
				/ (A2 - A1)
		except ZeroDivisionError:  # Protect from dividing by 0 in case APR=0%
			return 0
			
	return result

