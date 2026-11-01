/**
 * Eldercare — “About Your Parent” contact / lead form (2 sections).
 *
 * Paste into a dedicated Apps Script project as Code.gs.
 *
 * First time:
 *   createEldercareContactForm()
 *
 * Update questions (SAME form URL + SAME Sheet):
 *   updateEldercareContactForm()
 *
 * New URL only if intentional:
 *   createEldercareContactFormForceNew()
 *
 * Log links:
 *   logEldercareContactFormUrls()
 */

var ELDERCARE_CONTACT_FORM_KEY = 'ELDERCARE_CONTACT_FORM_ID';
var ELDERCARE_CONTACT_SHEET_KEY = 'ELDERCARE_CONTACT_SHEET_ID';

function createEldercareContactForm() {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty(ELDERCARE_CONTACT_FORM_KEY)) {
    throw new Error(
      'A contact form is already saved. Run updateEldercareContactForm() to keep ' +
        'the same URL, or createEldercareContactFormForceNew() for a new URL.'
    );
  }
  return provisionEldercareContactForm_({ forceNew: true });
}

function updateEldercareContactForm() {
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty(ELDERCARE_CONTACT_FORM_KEY)) {
    throw new Error(
      'No saved form ID. Run createEldercareContactForm() once first.'
    );
  }
  return provisionEldercareContactForm_({ forceNew: false });
}

function createEldercareContactFormForceNew() {
  return provisionEldercareContactForm_({ forceNew: true });
}

function logEldercareContactFormUrls() {
  var props = PropertiesService.getScriptProperties();
  var formId = props.getProperty(ELDERCARE_CONTACT_FORM_KEY);
  var sheetId = props.getProperty(ELDERCARE_CONTACT_SHEET_KEY);
  if (!formId) {
    Logger.log('No contact form saved yet.');
    return null;
  }
  var form = FormApp.openById(formId);
  var sheet = sheetId ? SpreadsheetApp.openById(sheetId) : null;
  return logEldercareContactUrls_(form, sheet);
}

function provisionEldercareContactForm_(opts) {
  var forceNew = opts && opts.forceNew;
  var props = PropertiesService.getScriptProperties();
  var form;
  var sheet;

  if (forceNew) {
    form = FormApp.create('Eldercare — About Your Parent');
    applyEldercareContactSettings_(form);
    sheet = createAndLinkEldercareContactSheet_(form);
    props.setProperty(ELDERCARE_CONTACT_FORM_KEY, form.getId());
    props.setProperty(ELDERCARE_CONTACT_SHEET_KEY, sheet.getId());
    Logger.log('Created NEW contact form + linked Sheet.');
  } else {
    form = FormApp.openById(props.getProperty(ELDERCARE_CONTACT_FORM_KEY));
    clearFormItemsContact_(form);
    applyEldercareContactSettings_(form);

    var sheetId = props.getProperty(ELDERCARE_CONTACT_SHEET_KEY);
    if (sheetId) {
      try {
        sheet = SpreadsheetApp.openById(sheetId);
      } catch (e) {
        sheet = null;
      }
    }
    if (!sheet) {
      sheet = createAndLinkEldercareContactSheet_(form);
      props.setProperty(ELDERCARE_CONTACT_SHEET_KEY, sheet.getId());
    } else {
      ensureFormSheetDestinationContact_(form, sheet.getId());
      Logger.log('Updated EXISTING contact form (URL unchanged).');
    }
  }

  buildEldercareContactFormContent_(form);
  return logEldercareContactUrls_(form, sheet);
}

function applyEldercareContactSettings_(form) {
  form
    .setTitle('Eldercare — About Your Parent')
    .setDescription(
      'Help us help elders stay safe and independent at home.\n\n' +
        'Share a few details about your parent. An Eldercare Advisor can follow up ' +
        'if you would like support. There is no obligation.'
    )
    .setAcceptingResponses(true)
    .setProgressBar(true)
    .setShuffleQuestions(false)
    .setCollectEmail(true); // Built-in Email * field on the form
}

function createAndLinkEldercareContactSheet_(form) {
  var sheet = SpreadsheetApp.create('Eldercare Contact — Responses');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
  return sheet;
}

function ensureFormSheetDestinationContact_(form, spreadsheetId) {
  try {
    if (form.getDestinationId() === spreadsheetId) return;
  } catch (e) {
    // no destination
  }
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheetId);
}

function clearFormItemsContact_(form) {
  // Same pattern as short survey — strip navigation, then delete.
  var items = form.getItems();
  var i;
  var item;
  var type;
  var mc;
  var values;

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
      } else if (type === FormApp.ItemType.PAGE_BREAK) {
        item.asPageBreakItem().setGoToPage(FormApp.PageNavigationType.CONTINUE);
      }
    } catch (e) {
      // continue
    }
  }

  var guard = 0;
  while (form.getItems().length > 0 && guard < 500) {
    guard++;
    items = form.getItems();
    item = items[items.length - 1];
    try {
      form.deleteItem(item);
    } catch (e1) {
      form.deleteItem(items.length - 1);
    }
  }
}

function logEldercareContactUrls_(form, sheet) {
  Logger.log('--- Eldercare Contact Form ---');
  Logger.log('Form ID: ' + form.getId());
  Logger.log('Edit URL: ' + form.getEditUrl());
  if (sheet) {
    Logger.log('Responses Sheet URL: ' + sheet.getUrl());
  }
  try {
    Logger.log('Published URL: ' + form.getPublishedUrl());
  } catch (e) {
    Logger.log('Publish from Form UI if needed; URL stays stable while Form ID is unchanged.');
  }
  return {
    formId: form.getId(),
    editUrl: form.getEditUrl(),
    sheetUrl: sheet ? sheet.getUrl() : null,
  };
}

function buildEldercareContactFormContent_(form) {
  /*
   * Section 1 — About Your Parent
   * (Email is collected automatically via setCollectEmail(true).)
   */

  form
    .addSectionHeaderItem()
    .setTitle('About Your Parent')
    .setHelpText(
      'Please tell us a little about the senior you care for. ' +
        'Your email is collected so we can follow up if you ask us to.'
    );

  form
    .addTextItem()
    .setTitle("Parent's Name")
    .setRequired(true);

  form
    .addTextItem()
    .setTitle('Age')
    .setRequired(true)
    .setHelpText('Approximate age is fine.');

  form
    .addTextItem()
    .setTitle('City')
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle('Lives Alone?')
    .setChoiceValues(['Yes', 'No'])
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle('Family lives outside Hyderabad?')
    .setChoiceValues(['Yes', 'No'])
    .setRequired(true);

  form
    .addTextItem()
    .setTitle('Primary Contact')
    .setRequired(true)
    .setHelpText('Name and phone / WhatsApp for the family member we should reach.');

  /*
   * Section 2 — Advisor contact preference
   */

  form
    .addPageBreakItem()
    .setTitle('Would you like us to reach out?')
    .setHelpText('Optional preference for an Eldercare Advisor follow-up.');

  form
    .addMultipleChoiceItem()
    .setTitle('Would you like an Eldercare Advisor to contact you?')
    .setChoiceValues(['Yes', 'No'])
    .setRequired(true);

  form
    .addMultipleChoiceItem()
    .setTitle('Preferred time:')
    .setChoiceValues(['Morning', 'Afternoon', 'Evening'])
    .setRequired(false)
    .setHelpText('Skip if you selected No above.');
}
