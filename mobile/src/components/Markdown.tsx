// Minimal markdown renderer for assistant replies and audit reports
// (headings, bullet/numbered lists, **bold**, _italic_, images). No extra dependency.
import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { usePalette } from '@/hooks';
import { authUrl } from '@/services/api';
import { fonts } from '@/theme';

function Inline({ text, style }: { text: string; style?: any }) {
  const parts = text.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).filter(Boolean);
  return (
    <Text style={style}>
      {parts.map((part, i) =>
        part.startsWith('**') ? (
          <Text key={i} style={{ fontFamily: fonts.bodyStrong }}>{part.slice(2, -2)}</Text>
        ) : part.startsWith('_') && part.endsWith('_') && part.length > 2 ? (
          <Text key={i} style={{ fontStyle: 'italic', opacity: 0.8 }}>{part.slice(1, -1)}</Text>
        ) : (
          <Text key={i}>{part}</Text>
        ),
      )}
    </Text>
  );
}

export default function Markdown({ text }: { text: string }) {
  const p = usePalette();
  const body = { fontFamily: fonts.body, fontSize: 15, lineHeight: 22, color: p.ink };
  return (
    <View>
      {text.split('\n').map((raw, i) => {
        const line = raw.trimEnd().replace(/[✅⚠️❗❌🔎]️?\s?/gu, '');
        if (!line.trim()) return <View key={i} style={{ height: 6 }} />;
        const img = line.match(/!\[[^\]]*\]\(([^)]+)\)/);
        if (img) {
          const uri = img[1].startsWith('http') ? img[1] : authUrl(img[1]);
          return <Image key={i} source={{ uri }} style={styles.img} resizeMode="cover" />;
        }
        if (line.startsWith('### '))
          return <Inline key={i} text={line.slice(4)} style={{ fontFamily: fonts.heading, fontSize: 16, color: p.primary, marginTop: 10, marginBottom: 2 }} />;
        if (line.startsWith('## '))
          return <Inline key={i} text={line.slice(3)} style={{ fontFamily: fonts.display, fontSize: 18, color: p.ink, marginVertical: 4 }} />;
        const bullet = line.match(/^\s*([-*]|\d+\.)\s+(.*)$/);
        if (bullet)
          return (
            <View key={i} style={styles.row}>
              <Text style={[body, styles.bullet, { color: p.inkSoft }]}>{/\d/.test(bullet[1]) ? bullet[1] : '•'}</Text>
              <Inline text={bullet[2]} style={[body, { flex: 1 }]} />
            </View>
          );
        return <Inline key={i} text={line.replace(/ {2}$/, '')} style={body} />;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 6, marginVertical: 1 },
  bullet: { width: 18, textAlign: 'right' },
  img: { width: '100%', aspectRatio: 4 / 3, borderRadius: 12, marginVertical: 8, backgroundColor: '#0003' },
});
