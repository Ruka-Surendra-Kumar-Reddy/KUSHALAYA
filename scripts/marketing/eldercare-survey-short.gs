/**
 * SHORT Eldercare customer discovery survey (~3–5 minutes).
 *
 * Focus: top concern, fall risk, paid support, safety product, lead service,
 * package preference, payer / price / membership.
 *
 * Paste into a NEW Apps Script project as Code.gs.
 *
 * First time (creates form + linked Sheet, saves IDs):
 *   createEldercareSurveyShort()
 *
 * Later question/copy changes (SAME form URL + SAME Sheet):
 *   updateEldercareSurveyShort()
 *
 * Only if you intentionally want a brand-new public URL:
 *   createEldercareSurveyShortForceNew()
 *
 * Script Properties (Project Settings → Script properties):
 *   ELDERCARE_SHORT_FORM_ID
 *   ELDERCARE_SHORT_SHEET_ID
 */

var ELDERCARE_SHORT_FORM_KEY = 'ELDERCARE_SHORT_FORM_ID';
var ELDERCARE_SHORT_SHEET_KEY = 'ELDERCARE_SHORT_SHEET_ID';

/** First-time create. Fails if a form ID is already saved (use update instead). */
function createEldercareSurveyShort() {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty(ELDERCARE_SHORT_FORM_KEY)) {
    throw new Error(
      'A survey form is already saved. Run updateEldercareSurveyShort() to keep ' +
        'the same URL, or createEldercareSurveyShortForceNew() for a new form URL.'
    );
  }
  return provisionEldercareSurveyShort_({ forceNew: true });
}

/**
 * Rebuild questions on the EXISTING form (same edit + respondent URL).
 * Keeps the linked responses Spreadsheet. Old response rows stay;
 * new/changed questions may add columns in the Sheet.
 */
function updateEldercareSurveyShort() {
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty(ELDERCARE_SHORT_FORM_KEY)) {
    throw new Error(
      'No saved form ID. Run createEldercareSurveyShort() once first.'
    );
  }
  return provisionEldercareSurveyShort_({ forceNew: false });
}

/** Creates a new form + sheet and overwrites saved IDs (new public URL). */
function createEldercareSurveyShortForceNew() {
  return provisionEldercareSurveyShort_({ forceNew: true });
}

/** Logs current saved URLs without changing the form. */
function logEldercareSurveyShortUrls() {
  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty(ELDERCARE_SHORT_FORM_KEY);
  var sheetId = props.getProperty(ELDERCARE_SHORT_SHEET_KEY);
  if (!formId) {
    Logger.log('No form saved yet. Run createEldercareSurveyShort().');
    return null;
  }
  var form = FormApp.openById(formId);
  var sheet = sheetId ? SpreadsheetApp.openById(sheetId) : null;
  return logEldercareShortUrls_(form, sheet);
}

function provisionEldercareSurveyShort_(opts) {
  var forceNew = opts && opts.forceNew;
  var props = PropertiesService.getScriptProperties();
  var form;
  var sheet;

  if (forceNew) {
    form = FormApp.create('Eldercare Survey (Short)');
    applyEldercareShortFormSettings_(form);
    sheet = createAndLinkEldercareShortSheet_(form);
    props.setProperty(ELDERCARE_SHORT_FORM_KEY, form.getId());
    props.setProperty(ELDERCARE_SHORT_SHEET_KEY, sheet.getId());
    Logger.log('Created NEW form and linked Sheet (IDs saved to Script Properties).');
  } else {
    form = FormApp.openById(props.getProperty(ELDERCARE_SHORT_FORM_KEY));
    clearFormItems_(form);
    applyEldercareShortFormSettings_(form);

    var sheetId = props.getProperty(ELDERCARE_SHORT_SHEET_KEY);
    if (sheetId) {
      try {
        sheet = SpreadsheetApp.openById(sheetId);
      } catch (e) {
        sheet = null;
      }
    }
    if (!sheet) {
      sheet = createAndLinkEldercareShortSheet_(form);
      props.setProperty(ELDERCARE_SHORT_SHEET_KEY, sheet.getId());
      Logger.log('Sheet missing — created and linked a new responses Sheet.');
    } else {
      ensureFormSheetDestination_(form, sheet.getId());
      Logger.log('Updated EXISTING form in place (URL unchanged). Sheet still linked.');
    }
  }

  buildEldercareSurveyShortContent_(form);
  return logEldercareShortUrls_(form, sheet);
}

function applyEldercareShortFormSettings_(form) {
  form
    .setTitle('Eldercare Survey (Short)')
    .setDescription(
      'Help us help elders stay safe, healthy, and independent at home.\n\n' +
        'This short survey (~3–5 minutes) is for seniors and for families who ' +
        'care about them. Your answers help Eldercare decide which products, ' +
        'services, and packages to offer in Hyderabad and beyond. There are ' +
        'no right or wrong answers.'
    )
    .setAcceptingResponses(true)
    .setProgressBar(true)
    .setShuffleQuestions(false)
    .setCollectEmail(false);
}

function createAndLinkEldercareShortSheet_(form) {
  var sheet = SpreadsheetApp.create('Eldercare Survey Short — Responses');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
  return sheet;
}

function ensureFormSheetDestination_(form, spreadsheetId) {
  try {
    var destId = form.getDestinationId();
    if (destId === spreadsheetId) return;
  } catch (e) {
    // No destination set yet.
  }
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheetId);
}

/**
 * Clear all form items safely.
 * Google Forms throws "Invalid data updating form" if you delete page breaks
 * that are still referenced by choice/page navigation — strip nav first.
 */
function clearFormItems_(form) {
  var items = form.getItems();
  var i;
  var item;
  var type;
  var mc;
  var values;
  var list;

  // 1) Remove go-to-page navigation from choices
  for (i = 0; i < items.length; i++) {
    item = items[i];
    type = item.getType();
    try {
      if (type === FormApp.ItemType.MULTIPLE_CHOICE) {
        mc = item.asMultipleChoiceItem();
        values = mc.getChoices().map(function (c) {
          return c.getValue();
        });
        mc.setChoiceValues(values);
      } else if (type === FormApp.ItemType.LIST) {
        list = item.asListItem();
        values = list.getChoices().map(function (c) {
          return c.getValue();
        });
        list.setChoiceValues(values);
      } else if (type === FormApp.ItemType.PAGE_BREAK) {
        item.asPageBreakItem().setGoToPage(FormApp.PageNavigationType.CONTINUE);
      }
    } catch (e) {
      Logger.log('Nav reset skipped for item ' + i + ': ' + e);
    }
  }

  // 2) Delete from the end (re-fetch each pass; some deletes shift indexes)
  var guard = 0;
  while (form.getItems().length > 0 && guard < 500) {
    guard++;
    items = form.getItems();
    item = items[items.length - 1];
    try {
      form.deleteItem(item);
    } catch (e1) {
      try {
        form.deleteItem(items.length - 1);
      } catch (e2) {
        Logger.log('Delete failed for last item: ' + e2);
        // Last resort: move on by attempting earlier items
        if (items.length < 2) {
          throw e2;
        }
        try {
          form.deleteItem(items[items.length - 2]);
        } catch (e3) {
          throw e2;
        }
      }
    }
  }
}

function logEldercareShortUrls_(form, sheet) {
  Logger.log('--- Eldercare Survey Short ---');
  Logger.log('Form ID: ' + form.getId());
  Logger.log('Edit URL (stable): ' + form.getEditUrl());
  if (sheet) {
    Logger.log('Responses Sheet ID: ' + sheet.getId());
    Logger.log('Responses Sheet URL (stable): ' + sheet.getUrl());
  }
  try {
    Logger.log('Published / respondent URL: ' + form.getPublishedUrl());
  } catch (e) {
    Logger.log(
      'Published URL unavailable via API — use Form → Send / Publish; ' +
        'it stays the same while Form ID is unchanged.'
    );
  }
  return {
    formId: form.getId(),
    editUrl: form.getEditUrl(),
    sheetId: sheet ? sheet.getId() : null,
    sheetUrl: sheet ? sheet.getUrl() : null,
  };
}

/**
 * Builds all questions + branching onto an empty (or cleared) Form.
 * @param {Form} form
 */
function buildEldercareSurveyShortContent_(form) {
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

  var paidSupportLast12Months = [
    'No paid support',
    'Domestic helper or maid',
    'Caregiver or attendant',
    'Nurse or physiotherapist',
    'Driver or appointment assistance',
    'Home repair or maintenance worker',
    'More than one of these',
    'Not sure',
  ];

  var safetyProducts = [
    'Bathroom grab bars',
    'Non-slip bathroom treatment',
    'Shower chair or bath bench',
    'Raised toilet seat',
    'Better night lighting',
    'Stair or entrance railing',
    'Wheelchair ramp',
    'Emergency SOS button or pendant',
    'Not sure',
    'None currently needed',
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

  var packages = [
    'Safety Starter — home assessment, safety report, grab bars, and emergency plan',
    'Health Support — appointment coordination, accompaniment, medication support, and nurse coordination',
    'Independent Living — home repairs, transportation, errands, and wellness check-ins',
    'Family Peace of Mind — regular visits, emergency coordination, care manager, and family updates',
    'Individual services only',
    'None of these',
  ];

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
  var sShared;
  var sNotEligible;
  var sThanks;

  form
    .addSectionHeaderItem()
    .setTitle('Help us help elders')
    .setHelpText(
      'Your experience — as a family member or as a senior — guides what we ' +
        'build next. Please select who is completing this survey.'
    );

  q1_1 = form
    .addMultipleChoiceItem()
    .setTitle('1.1 I am filling out this survey as:')
    .setChoiceValues(Q1_CHOICES)
    .setRequired(true);
  q1_1_id = q1_1.getId();

  /*
   * --------------------------------------------------------------------------
   * FAMILY PATH
   * --------------------------------------------------------------------------
   */

  s2 = form
    .addPageBreakItem()
    .setTitle('Family — quick screen')
    .setHelpText(
      'Answer about one senior parent or older relative (the person you are ' +
        'most concerned about).'
    );

  q2_1 = form
    .addMultipleChoiceItem()
    .setTitle(
      '2.1 Do you have one or more parents or close relatives aged 60 or older?'
    )
    .setChoiceValues(Q2_CHOICES)
    .setRequired(true);
  q2_1_id = q2_1.getId();

  s2b = form.addPageBreakItem().setTitle('Family — about the senior');

  addMcShort(
    form,
    "2.2 What is the senior's age bracket?",
    ['60–69 years', '70–79 years', '80–89 years', '90+ years', 'Not sure'],
    true,
    false
  );

  addMcShort(
    form,
    '2.3 Where does the senior currently live?',
    ['Hyderabad', 'Another city in India', 'Another country', 'Same home as me'],
    true,
    true
  );

  addMcShort(
    form,
    '2.4 Where do you currently live?',
    ['Hyderabad', 'Another city in India', 'Abroad / outside India'],
    true,
    true
  );

  form
    .addPageBreakItem()
    .setTitle('Family — needs and current behavior')
    .setHelpText('About the senior described above.');

  addMcShort(
    form,
    '3.1 Which ONE concern worries you most?',
    concerns,
    true,
    true
  );

  addMcShort(
    form,
    '3.2 Has the senior experienced a fall in the last two years?',
    ['Yes', 'No', 'Not sure'],
    true,
    false
  );

  addMcShort(
    form,
    '4.1 Has the senior used any paid support during the past 12 months?',
    paidSupportLast12Months,
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SENIOR PATH
   * --------------------------------------------------------------------------
   */

  s5 = form
    .addPageBreakItem()
    .setTitle('Seniors — about you')
    .setHelpText('Please answer about yourself.');

  q5_1 = form
    .addMultipleChoiceItem()
    .setTitle('5.1 What is your age bracket?')
    .setChoiceValues(Q5_CHOICES)
    .setRequired(true);
  q5_1_id = q5_1.getId();

  s5b = form.addPageBreakItem().setTitle('Seniors — household');

  addMcShort(
    form,
    '5.2 Where do you currently live?',
    ['Hyderabad', 'Another city in India', 'Another country'],
    true,
    true
  );

  addMcShort(
    form,
    '5.3 Do you live alone or with others?',
    [
      'Alone',
      'With spouse / partner',
      'With children or other family',
      'With a live-in helper / caregiver',
    ],
    true,
    true
  );

  form
    .addPageBreakItem()
    .setTitle('Seniors — needs and current behavior');

  addMcShort(
    form,
    '6.1 Which ONE concern worries you most about living at home as you get older?',
    concerns,
    true,
    true
  );

  addMcShort(
    form,
    '6.2 Have you experienced a fall in the last two years?',
    ['Yes', 'No', 'Not sure'],
    true,
    false
  );

  addMcShort(
    form,
    '7.1 Have you used any paid support during the past 12 months?',
    paidSupportLast12Months,
    true,
    false
  );

  /*
   * --------------------------------------------------------------------------
   * SHARED — product, service, package, payment, trust
   * --------------------------------------------------------------------------
   */

  sShared = form
    .addPageBreakItem()
    .setTitle('What to offer first')
    .setHelpText(
      'Please make a clear choice even if several options sound useful.'
    );

  addMcShort(
    form,
    '8.1 Which ONE home-safety improvement would be most useful today?',
    safetyProducts,
    true,
    false
  );

  addMcShort(
    form,
    '8.2 Which ONE service would you be most likely to purchase first?',
    mainServices,
    true,
    false
  );

  addMcShort(
    form,
    '8.3 If a trusted provider offered that service today, when would you realistically start?',
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

  addMcShort(
    form,
    '8.4 Which ONE package would be most appealing?',
    packages,
    true,
    false
  );

  form
    .addPageBreakItem()
    .setTitle('Paying for support')
    .setHelpText('These answers help us price fairly — no commitment.');

  addMcShort(
    form,
    '9.1 Who would most likely pay for the service?',
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

  addMcShort(
    form,
    '9.2 What would you consider a reasonable one-time price for a Professional Home Safety Assessment?',
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

  addMcShort(
    form,
    '9.3 Would you consider a monthly or annual membership for ongoing safety, coordination, and family updates?',
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

  form
    .addPageBreakItem()
    .setTitle('Optional contact')
    .setHelpText(
      'Optional. Used only for research follow-up or pilot access.'
    );

  form.addTextItem().setTitle('10.1 Name');
  form.addTextItem().setTitle('10.2 Phone / WhatsApp');
  form.addTextItem().setTitle('10.3 Email (optional)');

  sNotEligible = form
    .addPageBreakItem()
    .setTitle('Thank you')
    .setHelpText('Outside the target group for this survey.');

  form
    .addSectionHeaderItem()
    .setTitle('Thank you for your interest.')
    .setHelpText(
      'This survey is for people aged 60+ and family members supporting an ' +
        'older relative. Learn more at https://www.kushalaya.com'
    );

  sThanks = form.addPageBreakItem().setTitle('Thank you');

  form
    .addSectionHeaderItem()
    .setTitle('Thank you for your time!')
    .setHelpText(
      'Your answers help shape Eldercare.\n\n' +
        'Get your free 5-minute Parent Care Check:\n' +
        'https://www.kushalaya.com/parent-care-check'
    );

  applyNavShort(form, q1_1_id, [
    { text: Q1_CHOICES[0], page: s2 },
    { text: Q1_CHOICES[1], page: s5 },
    { text: Q1_CHOICES[2], page: s2 },
  ]);

  applyNavShort(form, q2_1_id, [
    { text: Q2_CHOICES[0], page: s2b },
    { text: Q2_CHOICES[1], page: sNotEligible },
  ]);

  applyNavShort(form, q5_1_id, [
    { text: Q5_CHOICES[0], page: sNotEligible },
    { text: Q5_CHOICES[1], page: s5b },
    { text: Q5_CHOICES[2], page: s5b },
    { text: Q5_CHOICES[3], page: s5b },
    { text: Q5_CHOICES[4], page: s5b },
  ]);

  s5.setGoToPage(sShared);
  sNotEligible.setGoToPage(sThanks);
  sThanks.setGoToPage(FormApp.PageNavigationType.SUBMIT);
}

function applyNavShort(form, itemId, pairs) {
  var item = form.getItemById(itemId).asMultipleChoiceItem();
  item.setChoices(
    pairs.map(function (p) {
      return item.createChoice(p.text, p.page);
    })
  );
  Logger.log(
    'Set ' + item.getChoices().length + ' choices on "' + item.getTitle() + '"'
  );
}

function addMcShort(form, title, values, required, showOther) {
  return form
    .addMultipleChoiceItem()
    .setTitle(title)
    .setChoiceValues(values)
    .showOtherOption(Boolean(showOther))
    .setRequired(Boolean(required));
}
