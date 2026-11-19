export const FORMATS = { post: "Пост", carousel: "Карусель", stories: "Stories", reels: "Reels", ad: "Реклама" };

export function topicColor(topic) {
  let hue = 0;
  for (const char of topic.toLocaleLowerCase("uk")) hue = (hue * 31 + char.codePointAt(0)) % 360;
  return { backgroundColor: `hsl(${hue} 35% 21%)`, color: `hsl(${hue} 58% 85%)` };
}
