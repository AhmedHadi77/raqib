// Turn a printable HTML page from the server into a PDF (phone) or the browser's print dialog (web).
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import { Platform } from 'react-native';

/** Returns a message to show, or null when a share sheet / print dialog opened. */
export async function exportHtmlAsPdf(html: string, title: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    const w = window.open('', '_blank');
    if (!w) throw new Error('Allow pop-ups to export the report');
    w.document.write(html);
    w.document.close();
    setTimeout(() => w.print(), 400);
    return null;
  }
  const { uri } = await Print.printToFileAsync({ html });
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(uri, { mimeType: 'application/pdf', dialogTitle: title, UTI: 'com.adobe.pdf' });
    return null;
  }
  return `Saved PDF: ${uri}`;
}
