/**
 * Creates the complete Eldercare customer discovery survey (Google Apps Script).
 *
 * How to use:
 * 1. Open https://script.google.com → New project
 * 2. Paste this file into Code.gs (or clasp push if linked)
 * 3. Run createEldercareSurvey()
 * 4. Open Executions / View → Logs for Edit URL, Sheet URL, Form ID
 *
 * IMPORTANT: Every execution creates a NEW Google Form and a linked Sheet.
 *
 * Fixes included vs early drafts:
 * - setAcceptingResponses (not setIsAcceptingResponses)
 * - Family screener 2.1 alone on its page so "No" skips 2.2+ and goes to not-eligible
 * - Senior age screener 5.1 alone on its page so "Under 60" skips 5.2+ and goes to not-eligible
 * - Responses destination = new Google Spreadsheet
 */

function createEldercareSurvey() {
  var form = FormApp.create('Eldercare Survey')
    .setDescription(
      'Help us help elders stay safe, healthy, and independent at home.\n\n' +
        'This short survey is for seniors and for families who care about them. ' +
        'It takes about 8–10 minutes. Your answers help Eldercare design reliable ' +
        'support in Hyderabad and beyond. There are no right or wrong answers.'
    )
    .setAcceptingResponses(true)
    .setProgressBar(true)
    .setShuffleQuestions(false)
    .setCollectEmail(false);

  // Link a Sheet so every response is recorded (Form UI → Responses → Spreadsheet).
  var sheet = SpreadsheetApp.create('Eldercare Survey — Responses');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  var concerns = [
    'Falling at home',
    'Medical emergencies',
    'Living alone',
    'Forgetting medications',
    'Home maintenance / repairs',
    'Security / safety of the home',
    'Loneliness / isolation',
    'Transportation / getting to appointments',
    'Memory issues',
    'Stairs, bathroom, or accessibility at home',
    'Finding trustworthy help',
  ];

  var supportList = [
    'Family living in the same home',
    'Family living nearby',
    'Neighbors or friends',
    'Domestic helper / maid',
    'Hired caregiver',
    'Private nurse',
    'Nobody regularly',
  ];

  var hydLocalities = [
    'Gachibowli / Financial District',
    'Kondapur / HITEC City',
    'Jubilee Hills / Banjara Hills',
    'Madhapur / Raidurg',
    'Kukatpally / Miyapur',
    'Tellapur / Nallagandla',
    'Secunderabad / Sainikpuri',
    'Begumpet / Ameerpet',
    'Uppal / Nagole',
    'LB Nagar / Dilsukhnagar',
    'Kompally / Suchitra',
    'Mehdipatnam / Tolichowki',
    'Attapur / Rajendranagar',
    'Manikonda / Narsingi',
  ];

  var mainServices = [
    'Professional Home Safety Assessment',
    'Bathroom / Home Safety Upgrades',
    'Hospital Visit Accompaniment',
    'Monthly Wellness & Companion Visits',
    'Home Maintenance / Repair Support',
    'Care Coordination & Emergency Plan',
    'In-Home Nursing / Physiotherapy',
    'Medication Support',
    'Transportation to Appointments',
    'Family Reports / Digital Portal',
    'None / Not ready to purchase',
  ];

  var q1_1;
  var q2_1;
  var q5_1;
  var q1_1_id;
  var q2_1_id;
  var q5_1_id;

  var s2;
  var s2b;
  var s5;
  var s5b;
  var s8;
  var s18;
  var s19;

  var Q1_CHOICES = [
    'An adult child or family member of someone aged 60 or older',
    'A senior aged 60 or older — answering about myself',
    'Both — I am 60+ and also support another older relative; I will answer about the relative I am most concerned about',
  ];
  var Q2_CHOICES = ['Yes', 'No'];
  var Q5_CHOICES = [
    'Under 60 years',
    '60–69 years',
    '70–79 years',
    '80–89 years',
    '90+ years',
  ];

  /*
   * --------------------------------------------------------------------------
   * SECTION 1 — START HERE
   * --------------------------------------------------------------------------
   */

  form
    .addSectionHeaderItem()
    .setTitle('Help us help elders')
    .setHelpText(
      'Your experience — as a family member or as a senior — guides what we ' +
        'build next. Please select the option that best describes who is ' +
        'completing this survey.'
    );

  // Set real labels immediately (avoids Google's default "Option 1").
  // Navigation destinations are applied at the end once page breaks exist.
  q1_1 = form
    .addMultipleChoiceItem()
    .setTitle('1.1 I am filling out this survey as:')
    .setChoiceValues(Q1_CHOICES)
    .setRequired(true);
  q1_1_id = q1_1.getId();

  /*
   * --------------------------------------------------------------------------
   * SECTION 2a — FAMILY SCREENER (2.1 alone — required for No → end)
   * --------------------------------------------------------------------------
   *
   * Google Forms only navigates on Next. Questions on the same page as a
   * branch question still appear. Keep the screener alone so "No" never
   * shows 2.2–2.6 (and never requires answering them).
   */

  s2 = form
    .addPageBreakItem()
    .setTitle('Section 2 — Family / Adult Children')
    .setHelpText(
      'Please answer about one senior parent or older relative. If you ' +
        'support more than one senior, answer about the person you are most ' +
        'concerned about.'
    );

  q2_1 = form
    .addMultipleChoiceItem()
    .setTitle(
      '2.1 Do you have one or more parents or close relatives aged 60 or older?'
    )
    .setChoiceValues(Q2_CHOICES)
    .setRequired(true);
  q2_1_id = q2_1.getId();

  /*
   * --------------------------------------------------------------------------
   * SECTION 2b — FAMILY DETAILS (only after Yes on 2.1)
   * --------------------------------------------------------------------------
   */

  s2b = form
    .addPageBreakItem()
    .setTitle('Section 2 — About the senior')
    .setHelpText('Continue with details about the senior you are most concerned about.');

  addMultipleChoice(
    form,
    "2.2 What is the senior's age bracket?",
    ['60–69 years', '70–79 years', '80–89 years', '90+ years', 'Not sure'],
    true,
    false
  );

  addMultipleChoice(
    form,
    '2.3 Where does the senior currently live?',
    ['Hyderabad', 'Another city in India', 'Another country', 'Same home as me'],
    true,
    true
  );

  addMultipleChoice(
    form,
    '2.4 If the senior lives in Hyderabad, which area or locality?',
    hydLocalities,
    false,
    true
  ).setHelpText('Skip this question if the senior does not live in Hyderabad.');

  addMultipleChoice(
    form,
    '2.5 Where do you currently live?',
    ['Hyderabad', 'Another city in India', 'Abroad / outside India'],
    true,
    true
  );

  addMultipleChoice(
    form,
    '2.6 How often do you see the senior in person?',
    ['Daily', 'Weekly', 'Monthly', 'Every few months', 'Once a year or less'],
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 3 — CURRENT CONCERNS: FAMILY
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 3 — Current Concerns')
    .setHelpText(
      'Please answer based on your concerns about the senior described above.'
    );

  addCheckbox(
    form,
    '3.1 What are your biggest concerns about your parent or older relative?',
    concerns,
    true,
    true
  );

  addMultipleChoice(
    form,
    '3.2 Which ONE concern worries you most?',
    concerns,
    true,
    true
  );

  addMultipleChoice(
    form,
    '3.3 Has the senior experienced a fall in the last two years?',
    ['Yes', 'No', 'Not sure'],
    true,
    false
  );

  form
    .addParagraphTextItem()
    .setTitle('3.4 If yes, what happened afterward?')
    .setHelpText(
      'Briefly describe any injury, hospital visit, recovery, change in ' +
        'mobility, or home modification.'
    );

  /*
   * --------------------------------------------------------------------------
   * SECTION 4 — CURRENT SUPPORT: FAMILY
   * --------------------------------------------------------------------------
   */

  form.addPageBreakItem().setTitle('Section 4 — Current Support');

  addCheckbox(
    form,
    '4.1 Who currently helps the senior day to day?',
    supportList,
    true,
    true
  );

  addMultipleChoice(
    form,
    '4.2 Approximately how much paid caregiving does the senior currently receive?',
    [
      'None',
      'Less than 10 hours per week',
      '10–30 hours per week',
      'Full-time daytime help',
      '24-hour / live-in caregiver',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '4.3 Have you ever hired someone to help the senior?',
    ['Yes', 'No', 'Not sure'],
    true,
    false
  );

  form
    .addTextItem()
    .setTitle('4.4 If yes, what service did you hire?')
    .setHelpText(
      'Examples: caregiver, nurse, physiotherapist, driver, companion, ' +
        'cleaner, or home repair professional.'
    );

  /*
   * --------------------------------------------------------------------------
   * SECTION 5a — SENIOR AGE SCREENER (5.1 alone)
   * --------------------------------------------------------------------------
   *
   * Navigation on s5 (this page break) sends family respondents from
   * Section 4 directly to Section 8, skipping all senior-only pages.
   */

  s5 = form
    .addPageBreakItem()
    .setTitle('Section 5 — Seniors: About You')
    .setHelpText('Please answer the following questions about yourself.');

  q5_1 = form
    .addMultipleChoiceItem()
    .setTitle('5.1 What is your age bracket?')
    .setChoiceValues(Q5_CHOICES)
    .setRequired(true);
  q5_1_id = q5_1.getId();

  /*
   * --------------------------------------------------------------------------
   * SECTION 5b — SENIOR DETAILS (only after age 60+)
   * --------------------------------------------------------------------------
   */

  s5b = form
    .addPageBreakItem()
    .setTitle('Section 5 — About your household')
    .setHelpText('Continue with a few details about where and how you live.');

  addMultipleChoice(
    form,
    '5.2 Where do you currently live?',
    ['Hyderabad', 'Another city in India', 'Another country'],
    true,
    true
  );

  addMultipleChoice(
    form,
    '5.3 If you live in Hyderabad, which area or locality?',
    hydLocalities,
    false,
    true
  ).setHelpText('Skip this question if you do not live in Hyderabad.');

  addMultipleChoice(
    form,
    '5.4 Do you live alone or with others?',
    [
      'Alone',
      'With spouse / partner',
      'With children or other family',
      'With a live-in helper / caregiver',
    ],
    true,
    true
  );

  addMultipleChoice(
    form,
    '5.5 How often do family members visit you in person?',
    [
      'Daily',
      'Weekly',
      'Monthly',
      'Every few months',
      'Once a year or less',
      'Not applicable',
    ],
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 6 — CURRENT CONCERNS: SENIOR
   * --------------------------------------------------------------------------
   */

  form.addPageBreakItem().setTitle('Section 6 — Current Concerns');

  addCheckbox(
    form,
    '6.1 What are your biggest concerns about living at home as you get older?',
    concerns,
    true,
    true
  );

  addMultipleChoice(
    form,
    '6.2 Which ONE concern worries you most?',
    concerns,
    true,
    true
  );

  addMultipleChoice(
    form,
    '6.3 Have you experienced a fall in the last two years?',
    ['Yes', 'No', 'Not sure'],
    true,
    false
  );

  form
    .addParagraphTextItem()
    .setTitle('6.4 If yes, what happened afterward?')
    .setHelpText(
      'Briefly describe any injury, hospital visit, recovery, change in ' +
        'mobility, or home modification.'
    );

  /*
   * --------------------------------------------------------------------------
   * SECTION 7 — CURRENT SUPPORT: SENIOR
   * --------------------------------------------------------------------------
   */

  form.addPageBreakItem().setTitle('Section 7 — Current Support');

  addCheckbox(
    form,
    '7.1 Who currently helps you day to day?',
    supportList,
    true,
    true
  );

  addMultipleChoice(
    form,
    '7.2 Approximately how much paid caregiving do you currently receive?',
    [
      'None',
      'Less than 10 hours per week',
      '10–30 hours per week',
      'Full-time daytime help',
      '24-hour / live-in caregiver',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '7.3 Have you or your family ever hired someone to help you at home?',
    ['Yes', 'No', 'Not sure'],
    true,
    false
  );

  form
    .addTextItem()
    .setTitle('7.4 If yes, what service was hired?')
    .setHelpText(
      'Examples: caregiver, nurse, physiotherapist, driver, companion, ' +
        'cleaner, or home repair professional.'
    );

  /*
   * --------------------------------------------------------------------------
   * SECTION 8 — HEALTH STATUS & HOME DIAGNOSTIC
   * --------------------------------------------------------------------------
   */

  s8 = form
    .addPageBreakItem()
    .setTitle('Section 8 — Health Status & Home Diagnostic')
    .setHelpText(
      'For family respondents, answer about the senior described earlier. ' +
        'For senior respondents, answer about yourself.'
    );

  addCheckbox(
    form,
    "8.1 Which of these best describe the senior's current needs?",
    [
      'Difficulty walking or unstable balance',
      'Vision difficulties',
      'Hearing difficulties',
      'Memory or cognitive difficulties',
      'Needs assistance bathing or dressing',
      'Needs assistance using the toilet',
      'Needs assistance cooking or preparing meals',
      'Needs assistance shopping or running errands',
      'Needs assistance managing medications',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '8.2 How does the senior usually move around at home?',
    [
      'No difficulty and no mobility aid',
      'Uses a cane',
      'Uses a walker / rollator',
      'Uses a wheelchair occasionally',
      'Uses a wheelchair most of the time',
      'Mostly confined to bed',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '8.3 What type of home does the senior live in?',
    [
      'Independent house',
      'Apartment',
      'Villa',
      'Gated community house / villa',
      'Senior living or assisted-living facility',
    ],
    true,
    true
  );

  addMultipleChoice(
    form,
    '8.4 What floor does the senior primarily live on?',
    [
      'Ground floor',
      '1st floor',
      '2nd floor',
      '3rd floor or above',
      'Multiple floors within the home',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '8.5 Is an elevator available and usable?',
    [
      'Yes',
      'No',
      'Not applicable — ground-floor home',
      'An elevator exists but is not always usable',
      'Not sure',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '8.6 Which stairs does the senior regularly use?',
    [
      'No stairs regularly used',
      'Steps or stairs at the entrance',
      'Stairs inside the home',
      'Building stairs because no elevator is available',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '8.7 What type of toilet does the senior primarily use?',
    [
      'Western-style seated toilet',
      'Indian-style squat toilet',
      'Both types are available',
      'Not sure',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '8.8 Which safety or mobility devices are currently available?',
    [
      'Bathroom grab bars',
      'Shower chair or bath bench',
      'Raised toilet seat',
      'Toilet safety frame',
      'Non-slip bathroom flooring or treatment',
      'Wheelchair ramp',
      'Stair railings',
      'Walker / rollator',
      'Wheelchair',
      'Hospital or adjustable bed',
      'Emergency SOS alarm or pendant',
      'Motion-activated night lights',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '8.9 Which ONE home improvement would make the biggest difference today?',
    [
      'Bathroom grab bars',
      'Non-slip bathroom flooring',
      'Shower chair or bath bench',
      'Raised toilet seat or toilet safety frame',
      'Stair or entrance railings',
      'Better lighting / night lighting',
      'Larger bathroom accessibility modification',
      'Wheelchair ramp',
      'Emergency SOS alarm',
      'Not sure',
      'No improvement currently needed',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '8.10 Does anyone stay in the home with the senior overnight?',
    ['Yes, every night', 'Yes, on some nights', 'No', 'Not sure'],
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 9 — SERVICE CATEGORIES
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 9 — Services You Might Use')
    .setHelpText(
      'Select only the services you would realistically consider using if ' +
        'they were reliable and reasonably priced.'
    );

  addCheckbox(
    form,
    '9.1 Which safety services would you realistically consider using?',
    [
      'Professional Home Safety Assessment',
      'Personalized Home Safety Report',
      'Fall-prevention recommendations',
      'Bathroom safety upgrades',
      'Grab-bar or safety-device installation',
      'Non-slip floor treatment',
      'Emergency response plan and setup',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '9.2 Which health and medical support services would you realistically consider using?',
    [
      'Hospital visit accompaniment',
      'Doctor appointment booking and coordination',
      'In-home physiotherapy',
      'In-home nurse visits',
      'Blood sample collection at home',
      'Medicine delivery',
      'Medication reminders or pill organization',
      'Vital-sign monitoring',
      'Post-surgery recovery support',
      'Medical equipment rental or coordination',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '9.3 Which home maintenance services would you realistically consider using?',
    [
      'Plumbing repairs',
      'Electrical repairs',
      'AC servicing',
      'Appliance repairs',
      'Pest control',
      'House cleaning',
      'Deep cleaning',
      'Gardening',
      'Painting',
      'General handyman services',
      'Home repair inspection and coordination',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '9.4 Which mobility and transportation services would you realistically consider using?',
    [
      'Wheelchair assistance',
      'Walker or wheelchair selection assistance',
      'Custom ramp installation',
      'Stair or entrance railing installation',
      'Transportation to doctor or hospital appointments',
      'Wheelchair-accessible transportation',
      'Assistance getting in and out of the home',
      'Airport or railway-station assistance',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '9.5 Which companionship and lifestyle services would you realistically consider using?',
    [
      'Friendly companion visits',
      'Weekly wellness check-ins',
      'Help making video calls to family',
      'Reading, games, conversation, or social engagement',
      'Walking companion',
      'Religious, spiritual, or temple visits',
      'Festival, family-event, or celebration assistance',
      'Shopping or errand assistance',
      'Grocery or medicine pickup',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '9.6 Which care coordination services would you realistically consider using?',
    [
      'Caregiver recruitment',
      'Caregiver attendance and performance supervision',
      'Doctor visit coordination',
      'Hospital discharge coordination',
      'Home repair management',
      'Emergency handling and family notification',
      'Monthly health and status reports for family',
      'Dedicated Elder Care Manager',
      'Checking the senior or home while family is away',
      'Bill payment or administrative assistance',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  addCheckbox(
    form,
    '9.7 Which technology or monitoring options would you realistically consider using?',
    [
      'Family digital portal',
      'Emergency SOS button or pendant',
      'Video updates after authorized home visits',
      'Automatic emergency monitoring using optional sensors',
      'Medication reminder technology',
      'Fall or inactivity alerts',
      'Personalized digital safety report',
      'Monthly family status dashboard',
      'None of these — do not select with another option',
    ],
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 10 — FORCED CHOICE & PURCHASE INTENT
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 10 — Priority and Purchase Intent')
    .setHelpText(
      'These questions ask you to make a choice, even if several services ' +
        'sound useful.'
    );

  addMultipleChoice(
    form,
    '10.1 If you could purchase only ONE service in the next 30 days, which would it be?',
    mainServices,
    true,
    false
  );

  addMultipleChoice(
    form,
    '10.2 Which ONE additional service would you be most likely to add later?',
    mainServices,
    true,
    false
  );

  addMultipleChoice(
    form,
    '10.3 If a trusted provider offered your selected service today, when would you realistically start?',
    [
      'Immediately',
      'Within 30 days',
      'Within 3 months',
      'Within 6 months',
      'Maybe later than 6 months',
      'Probably never',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '10.4 If Eldercare could solve only ONE problem, which should it solve first?',
    [
      'Keeping the senior safe at home',
      'Preventing falls and bathroom injuries',
      'Responding to emergencies',
      'Getting the senior to appointments',
      'Finding trustworthy caregivers and workers',
      'Managing healthcare and medications',
      'Maintaining and repairing the home',
      'Reducing loneliness',
      'Giving distant family peace of mind',
    ],
    true,
    true
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 11 — PACKAGE VALIDATION
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 11 — Package Validation')
    .setHelpText(
      'The examples below are early package ideas. Pricing is not yet final.'
    );

  addMultipleChoice(
    form,
    '11.1 Which package sounds most appealing?',
    [
      'Safety Starter — home safety assessment, personalized report, bathroom grab bars, and emergency plan',
      'Health Connect — appointment coordination, accompaniment, transportation, medication reminders, and nurse coordination',
      'Independent Living — home repairs, cleaning coordination, transportation, errands, and wellness check-ins',
      'Family Peace of Mind — regular visits, emergency coordination, dedicated care manager, and family reports',
      'Complete Support — safety, health, home maintenance, emergency coordination, and a dedicated care manager',
      'None of these',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '11.2 Which package structure would you prefer?',
    [
      'Choose individual services only',
      'A low-cost basic package with optional add-ons',
      'A mid-level monthly package covering common needs',
      'A comprehensive package with a dedicated care manager',
      'Not sure',
    ],
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 12 — FREQUENCY, DECISION-MAKER, PAYER & PRICING
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 12 — Frequency and Payment Preferences');

  form
    .addGridItem()
    .setTitle('12.1 How often would you realistically use each ongoing service?')
    .setRows([
      'Wellness or companion visits',
      'Hospital or doctor appointment assistance',
      'Home maintenance coordination',
      'Medication support',
      'Transportation assistance',
      'Care manager and family reporting',
    ])
    .setColumns([
      'Would not use',
      'As needed',
      'Every few months',
      'Monthly',
      'Weekly or more',
    ])
    .setRequired(true);

  addMultipleChoice(
    form,
    '12.2 How would you prefer to pay for ongoing support?',
    [
      'Pay per visit or per service',
      'Purchase prepaid service credits',
      'Monthly subscription',
      'Annual membership',
      'Basic membership plus pay-per-use services',
      'Depends on the service',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '12.3 Who would have the greatest influence on the purchase decision?',
    [
      'The senior',
      'Adult child or family member',
      'Senior and family jointly',
      'Doctor or healthcare professional',
      'Another person',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '12.4 Who would most likely pay for the service?',
    [
      'The senior',
      'Adult child living in Hyderabad',
      'Adult child living elsewhere in India',
      'Adult child living abroad / NRI',
      'Several family members sharing the cost',
      'Employer benefit or insurance',
      'Government or NGO support',
      'Depends on the price',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    "12.5 Which best describes the senior household's approximate monthly income?",
    [
      'Under ₹50,000',
      '₹50,000–₹1 lakh',
      '₹1–₹2 lakhs',
      '₹2–₹5 lakhs',
      'More than ₹5 lakhs',
      'Do not know',
      'Prefer not to answer',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '12.6 What would you consider a reasonable one-time price for a Professional Home Safety Assessment?',
    [
      'Under ₹1,000',
      '₹1,000–₹2,500',
      '₹2,501–₹5,000',
      '₹5,001–₹10,000',
      'More than ₹10,000',
      'Would expect this to be free',
      'Not sure',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '12.7 Would you consider paying a monthly or annual membership for safety, health, repair coordination, emergency support, and family updates?',
    [
      'Definitely would',
      'Probably would',
      'Might or might not',
      'Probably would not',
      'Definitely would not',
    ],
    true,
    false
  );

  addMultipleChoice(
    form,
    '12.8 What matters most when choosing an elder-support provider?',
    [
      'Safety and quality of care',
      'Reliable, background-verified staff',
      'Affordable price',
      'Fast availability',
      'A doctor or hospital recommendation',
      'Regular family communication',
      'Independence and dignity for the senior',
    ],
    true,
    true
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 13 — PAIN FREQUENCY
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 13 — Needs Experienced in the Past 12 Months');

  form
    .addGridItem()
    .setTitle(
      '13.1 During the past 12 months, how often did the senior or family encounter each need?'
    )
    .setRows([
      'Home safety or fall-risk concerns',
      'Hospital or urgent doctor visits',
      'Difficulty finding trustworthy help',
      'Home repair or maintenance issues',
      'Loneliness or need for companionship',
      'Medication tracking or management',
      'Emergency care situations',
      'Managing care while family was away',
    ])
    .setColumns(['Never', 'Once', '2–3 times', 'Monthly', 'Weekly or more'])
    .setRequired(true);

  /*
   * --------------------------------------------------------------------------
   * SECTION 14 — ALTERNATIVES & PAST BEHAVIOR
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 14 — Alternatives and Past Behavior');

  addCheckbox(
    form,
    '14.1 If Eldercare did not exist, how would you handle different elder-care needs?',
    [
      'Rely on family members',
      'Ask neighbors or friends',
      'Use an app or marketplace such as Urban Company',
      'Hire independent local workers, maids, or caregivers',
      'Ask a doctor or hospital for a recommendation',
      'Ask an apartment association or building staff',
      'Search through Google, Justdial, or social media',
      'Do not know where to find help',
    ],
    true,
    true
  );

  addMultipleChoice(
    form,
    '14.2 The last time a hospital or urgent doctor visit was needed, how was it handled?',
    [
      'The senior or local family handled it',
      'A relative traveled to assist',
      'A neighbor or friend helped',
      'A driver or private cab was hired',
      'A professional caregiver was hired',
      'An ambulance was used',
      'Help could not be arranged easily',
      'This has not occurred',
    ],
    true,
    true
  );

  addMultipleChoice(
    form,
    '14.3 The last time home maintenance was needed, how was it handled?',
    [
      'The senior or local family handled it',
      'A relative arranged it remotely',
      'A known neighborhood worker was used',
      'An app or online service was used',
      'Apartment or building staff handled it',
      'It could not be fixed quickly',
      'This has not occurred',
    ],
    true,
    true
  );

  addMultipleChoice(
    form,
    '14.4 The last time loneliness or being alone was a concern, what happened?',
    [
      'Family called or video-called',
      'A relative, neighbor, or friend visited',
      'A helper or companion was hired',
      'The senior attended a social or religious activity',
      'Nothing was arranged',
      'This has not been a concern',
    ],
    false,
    true
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 15 — TRUST, SECURITY & REFERRAL CHANNELS
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 15 — Trust, Security and Referral Channels');

  addCheckbox(
    form,
    '15.1 Which of the following would increase your trust in Eldercare?',
    [
      'Doctor or hospital recommendation',
      'Physiotherapist recommendation',
      'Apartment association endorsement',
      'NGO or senior-welfare association partnership',
      'Government registration or recognition',
      'Online reviews and testimonials',
      'Personal recommendation from friends or family',
      'Background-verified staff credentials',
      'Service guarantee and clear complaint process',
      'Ability for family to track visits and receive updates',
    ],
    true,
    false
  );

  form
    .addParagraphTextItem()
    .setTitle(
      '15.2 What security measures would make you comfortable allowing a professional into the home?'
    )
    .setHelpText(
      'Examples: ID badge, background check, female staff option, visit OTP, ' +
        'GPS tracking, family notification, uniform, or hospital referral.'
    );

  addMultipleChoice(
    form,
    '15.3 How did you receive this survey?',
    [
      'Friend or relative',
      'WhatsApp group or message',
      'Facebook',
      'Instagram',
      'LinkedIn',
      'Apartment association',
      'Doctor, hospital, or physiotherapist',
      'Senior organization or NGO',
    ],
    true,
    true
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 16 — FINAL THOUGHTS & FREE ASSESSMENT
   * --------------------------------------------------------------------------
   */

  form.addPageBreakItem().setTitle('Section 16 — Final Thoughts');

  form
    .addParagraphTextItem()
    .setTitle(
      '16.1 If you could solve just ONE problem related to aging safely at home, what would it be?'
    );

  form
    .addParagraphTextItem()
    .setTitle(
      '16.2 Is there a service, product, or type of support we have not included?'
    );

  addMultipleChoice(
    form,
    '16.3 Would you try a free 5-minute online Parent Care Check?',
    ['Yes', 'Maybe', 'No'],
    true,
    false
  ).setHelpText(
    'The Parent Care Check is a short digital assessment of home-safety and care needs.'
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 17 — OPTIONAL CONTACT DETAILS
   * --------------------------------------------------------------------------
   */

  form
    .addPageBreakItem()
    .setTitle('Section 17 — Optional Contact Details')
    .setHelpText(
      'Providing contact information is optional. Eldercare will use it ' +
        'only for research follow-up, pilot access, or the Parent Care Check.'
    );

  form.addTextItem().setTitle('17.1 Name');

  form.addTextItem().setTitle('17.2 Phone number / WhatsApp');

  var emailItem = form.addTextItem().setTitle('17.3 Email address');

  /*
   * Optional email format check. Question remains optional (not required).
   * If blank responses fail validation in your account, remove setValidation.
   */
  emailItem.setValidation(
    FormApp.createTextValidation()
      .requireTextIsEmail()
      .setHelpText('Enter a valid email address or leave this question blank.')
      .build()
  );

  /*
   * --------------------------------------------------------------------------
   * SECTION 18 — NOT ELIGIBLE
   * --------------------------------------------------------------------------
   */

  s18 = form
    .addPageBreakItem()
    .setTitle('Section 18 — Thank You')
    .setHelpText('This respondent is outside the target group for this survey.');

  form
    .addSectionHeaderItem()
    .setTitle('Thank you for your interest.')
    .setHelpText(
      'This survey is designed for people aged 60 or older and family ' +
        'members supporting an older relative. You can learn more about ' +
        'Eldercare at https://www.kushalaya.com'
    );

  /*
   * --------------------------------------------------------------------------
   * SECTION 19 — ELIGIBLE COMPLETION PAGE
   * --------------------------------------------------------------------------
   */

  s19 = form.addPageBreakItem().setTitle('Section 19 — Thank You');

  form
    .addSectionHeaderItem()
    .setTitle('Thank you for your valuable time and input!')
    .setHelpText(
      'Your responses will help shape Eldercare products, services, and ' +
        'care packages. Try the free Parent Care Check at ' +
        'https://www.kushalaya.com/parent-care-check'
    );

  /*
   * --------------------------------------------------------------------------
   * APPLY BRANCHING AFTER ALL DESTINATION SECTIONS EXIST
   * --------------------------------------------------------------------------
   *
   * Re-fetch items by ID, then setChoices with page navigation.
   * (Leaving a MC item empty first yields Google's default "Option 1".)
   */

  applyPageNavigationChoices(form, q1_1_id, [
    { text: Q1_CHOICES[0], page: s2 },
    { text: Q1_CHOICES[1], page: s5 },
    { text: Q1_CHOICES[2], page: s2 },
  ]);

  applyPageNavigationChoices(form, q2_1_id, [
    { text: Q2_CHOICES[0], page: s2b },
    { text: Q2_CHOICES[1], page: s18 },
  ]);

  applyPageNavigationChoices(form, q5_1_id, [
    { text: Q5_CHOICES[0], page: s18 },
    { text: Q5_CHOICES[1], page: s5b },
    { text: Q5_CHOICES[2], page: s5b },
    { text: Q5_CHOICES[3], page: s5b },
    { text: Q5_CHOICES[4], page: s5b },
  ]);

  /*
   * PageBreakItem.setGoToPage controls navigation after the page BEFORE
   * that page break.
   *
   * s5 begins the senior screener, so this sends family respondents
   * (finishing Section 4) to Section 8 — skipping Sections 5–7.
   */
  s5.setGoToPage(s8);

  /*
   * After Section 17 (eligible path), skip not-eligible page → thank you.
   */
  s18.setGoToPage(s19);

  /*
   * After Section 18 (not eligible), submit.
   */
  s19.setGoToPage(FormApp.PageNavigationType.SUBMIT);

  Logger.log('Eldercare Survey created successfully.');
  Logger.log('Form ID: ' + form.getId());
  Logger.log('Edit URL: ' + form.getEditUrl());
  Logger.log('Responses Sheet ID: ' + sheet.getId());
  Logger.log('Responses Sheet URL: ' + sheet.getUrl());
  try {
    Logger.log('Published Survey URL: ' + form.getPublishedUrl());
  } catch (e) {
    Logger.log('Published URL unavailable; open Edit URL and publish from the UI.');
  }

  return {
    formId: form.getId(),
    editUrl: form.getEditUrl(),
    sheetId: sheet.getId(),
    sheetUrl: sheet.getUrl(),
  };
}

/**
 * Replace MC choices and attach Go-to-section navigation.
 * @param {Form} form
 * @param {number} itemId
 * @param {{text: string, page: PageBreakItem}[]} pairs
 */
function applyPageNavigationChoices(form, itemId, pairs) {
  var item = form.getItemById(itemId).asMultipleChoiceItem();
  var choices = pairs.map(function (p) {
    return item.createChoice(p.text, p.page);
  });
  item.setChoices(choices);
  Logger.log(
    'Set ' +
      item.getChoices().length +
      ' choices on item "' +
      item.getTitle() +
      '"'
  );
}

/**
 * @param {Form} form
 * @param {string} title
 * @param {string[]} values
 * @param {boolean} required
 * @param {boolean} showOther
 * @return {MultipleChoiceItem}
 */
function addMultipleChoice(form, title, values, required, showOther) {
  if (!form) throw new Error('A valid Google Form is required.');
  if (!title || !values || values.length === 0) {
    throw new Error('Multiple-choice questions require a title and choices.');
  }
  return form
    .addMultipleChoiceItem()
    .setTitle(title)
    .setChoiceValues(values)
    .showOtherOption(Boolean(showOther))
    .setRequired(Boolean(required));
}

/**
 * @param {Form} form
 * @param {string} title
 * @param {string[]} values
 * @param {boolean} required
 * @param {boolean} showOther
 * @return {CheckboxItem}
 */
function addCheckbox(form, title, values, required, showOther) {
  if (!form) throw new Error('A valid Google Form is required.');
  if (!title || !values || values.length === 0) {
    throw new Error('Checkbox questions require a title and choices.');
  }
  return form
    .addCheckboxItem()
    .setTitle(title)
    .setChoiceValues(values)
    .showOtherOption(Boolean(showOther))
    .setRequired(Boolean(required));
}
